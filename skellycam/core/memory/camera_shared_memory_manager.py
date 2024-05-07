import logging
import multiprocessing
from multiprocessing import shared_memory
from typing import List

import numpy as np

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.detection.video_resolution import VideoResolution
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory
from skellycam.core.memory.shared_memory_demo import camera_ids, manager, shm, test_image, index, retrieved_image, \
    loop_count

BUFFER_SIZE = 1024 * 1024 * 1024  # 1 GB buffer size for all cameras

logger = logging.getLogger(__name__)


class CameraSharedMemoryManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 total_buffer_size: int = BUFFER_SIZE,
                 # existing_shared_memory: shared_memory.SharedMemory = None
                 ):
        self._camera_configs = camera_configs
        self._total_buffer_size = total_buffer_size
        buffer_size_per_camera = total_buffer_size // len(camera_configs)
        self._buffer_by_camera = {camera_id: CameraSharedMemory.from_config(camera_config=config,
                                                                            buffer_size=buffer_size_per_camera)
                                  for camera_id, config in self._camera_configs.items()}





    def _calculate_offsets(self, camera_ids: List[CameraId]):
        self.image_offsets = np.arange(0, self.buffer_size, self.image_size)
        self.max_offsets_per_camera = len(self.image_offsets) // len(camera_ids)
        self.offsets_by_camera = {}
        for index, camera_id in enumerate(camera_ids):
            offsets: List[int] = list(
                self.image_offsets[index * self.max_offsets_per_camera:(index + 1) * self.max_offsets_per_camera])
            self.offsets_by_camera[camera_id] = offsets
        self.next_index_by_camera = {camera_id: 0 for camera_id in camera_ids}

    @property
    def shared_memory_name(self) -> str:
        """
        Returns the name of the shared memory buffer, which can be used to access the buffer from other processes.
        example:
        ```
        # Create a shared memory buffer
        manager = SharedImageMemoryManager(image_shape=(480, 640, 3))
        #...
        # Retrieve the shared memory buffer using the  shared memory name
        existing_shm = shared_memory.SharedMemory(name=manager.shared_memory_name)
        other_manager = SharedImageMemoryManager(existing_shared_memory=existing_shm)
        ```
        """
        return self.shm.name

    @property
    def buffer_size_str(self) -> str:
        """
        Returns a human-readable string of the buffer size.
        """
        if len(str(self.buffer_size)) > 9:
            return f"{self.buffer_size / 1024 ** 3:.2f} GB"
        elif len(str(self.buffer_size)) > 6:
            return f"{self.buffer_size / 1024 ** 2:.2f} MB"
        elif len(str(self.buffer_size)) > 3:
            return f"{self.buffer_size / 1024:.2f} KB"
        else:
            return f"{self.buffer_size} bytes"

    def put_image(self,
                  image: np.ndarray,
                  camera_id: CameraId) -> int:
        """
        Put an image into the shared memory buffer and return the index at which it was stored.
        """

        with self._lock:
            if image.shape != self.image_shape:
                raise ValueError(
                    f"Input image shape ({image.shape}) does not match the defined shape for the shared memory ({self.image_shape}).")
            if image.dtype != self.image_dtype:
                raise ValueError(
                    f"Input image dtype ({image.dtype}) does not match the defined dtype for the shared memory ({self.image_dtype}).")

            if self.next_index_by_camera[camera_id] >= self.max_offsets_per_camera:
                self.next_index_by_camera[camera_id] = 0

            current_index = self.next_index_by_camera[camera_id]

            offset = self.offsets_by_camera[camera_id][current_index]
            # Determine the correct size of the slice of the shared memory buffer
            buffer_slice_size = self.image_size
            if offset + buffer_slice_size > self.buffer_size:
                raise ValueError(
                    f"Offset {offset} + buffer slice size {buffer_slice_size} exceeds buffer size {self.buffer_size}.")

            shm_array = np.ndarray(self.image_shape,
                                   dtype=self.image_dtype,
                                   buffer=self.shm.buf[offset:offset + buffer_slice_size])
            np.copyto(shm_array, image)

            self.next_index_by_camera[camera_id] += 1
            return current_index

    def get_image(self, index: int, camera_id: CameraId) -> np.ndarray:
        """
        Get an image from the shared memory buffer using the specified index.
        """
        with self._lock:
            offset = self.offsets_by_camera[camera_id][index]
            # Create a NumPy array from the shared memory buffer
            image_shared = np.ndarray(self.image_shape, dtype=self.image_dtype,
                                      buffer=self.shm.buf[offset:offset + self.image_size]).copy()

            return image_shared

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()

