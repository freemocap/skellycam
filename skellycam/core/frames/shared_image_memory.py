import logging
import multiprocessing
from multiprocessing import shared_memory
from typing import List

import numpy as np
from pydantic import BaseModel

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.detection.video_resolution import VideoResolution
from skellycam.core.frames.frame_payload import FramePayload

BUFFER_SIZE = 1024 * 1024 * 1024  # 1 GB buffer size for all cameras

logger = logging.getLogger(__name__)


class SharedPayloadMemoryManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 payload_model: BaseModel = FramePayload,
                 total_buffer_size: int = BUFFER_SIZE,
                 # existing_shared_memory: shared_memory.SharedMemory = None
                 ):
        self._camera_configs = camera_configs
        self._payload_model = payload_model
        self._total_buffer_size = total_buffer_size

    def allocate_shared_memory(self):
        self._calculate_buffer_sizes()

    def _calculate_buffer_sizes(self):
        self._number_of_cameras = len(self._camera_configs)
        self.image_shape = (image_resolution.height, image_resolution.width, color_channels)
        self.image_dtype = image_dtype
        self.image_size = np.prod(self.image_shape) * np.dtype(self.image_dtype).itemsize  # bytes
        self.buffer_size = buffer_size  # bytes
        self.max_images = buffer_size // self.image_size

        self._get_or_create_shared_memory(existing_shared_memory)

        self._calculate_offsets(camera_ids)

        self._lock = multiprocessing.Lock()

    def _get_or_create_shared_memory(self, existing_shared_memory: shared_memory.SharedMemory = None):
        if existing_shared_memory is not None:
            logger.debug(
                f"Recreating SharedImageMemoryManager from existing shared memory buffer - {existing_shared_memory.name}")
            self.shm = existing_shared_memory
        else:
            self.shm = shared_memory.SharedMemory(create=True, size=self.buffer_size)
            logger.debug(
                f"Created SharedImageMemoryManager with shared memory buffer - {self.shm.name} with size {self.buffer_size_str}")

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


## uncomment the following code and run this file as a script to test the shared memory manager relative to pipes

def send_images(camera_ids, pipe, image_shape, image_dtype, loop_count):
    test_image = np.random.randint(0, 255, size=image_shape, dtype=image_dtype)
    for i in range(loop_count):
        for camera_id in camera_ids:
            pipe.send(test_image)


def recv_images(pipe, image_shape, image_dtype, loop_count):
    for i in range(loop_count):
        retrieved_image = pipe.recv()


if __name__ == "__main__":
    import time

    logger.setLevel(logging.DEBUG)

    camera_ids = [CameraId(0), CameraId(1), CameraId(2)]
    manager = SharedPayloadMemoryManager(
        camera_ids=camera_ids,
        image_resolution=VideoResolution(width=1920, height=1080),
    )
    print(f"Shared memory name: {manager.shared_memory_name}")
    shm = shared_memory.SharedMemory(name=manager.shared_memory_name)
    print(f"Shared memory size: {shm.size}")
    test_image = np.random.randint(0, 255, size=manager.image_shape, dtype=manager.image_dtype)
    for camera_id in camera_ids:
        print(f"Camera{camera_id} - Test image shape: {test_image.shape}")
        print(f"Camera{camera_id} - Test image dtype: {test_image.dtype}")
        index = manager.put_image(image=test_image,
                                  camera_id=camera_id)
        print(f"Camera{camera_id} - Image index: {index}")
        retrieved_image = manager.get_image(index=index,
                                            camera_id=camera_id)
        print(f"Camera{camera_id} - Retrieved image shape: {retrieved_image.shape}")
        print(f"Camera{camera_id} - Retrieved image dtype: {retrieved_image.dtype}")
        print(f"Camera{camera_id} - Retrieved image checksum: {np.sum(retrieved_image)}")

    loop_count = 1000
    print("SHARED MEMORY TEST -  Sending and receiving 1000 1920x1080x3 images.")
    tik = time.perf_counter()
    for i in range(loop_count):
        for camera_id in camera_ids:
            index = manager.put_image(image=test_image,
                                      camera_id=camera_id)
            retrieved_image = manager.get_image(index=index,
                                                camera_id=camera_id)
    shared_memory_time_elapsed = time.perf_counter() - tik
    print(
        f"SHARED MEMORY - {loop_count} loops completed in {shared_memory_time_elapsed:.6f} seconds ({shared_memory_time_elapsed / loop_count:.6f} seconds per loop, or {1 / (shared_memory_time_elapsed / loop_count):.2f} loops per second).")

    print("PIPE TEST - Sending and receiving 1000 1920x1080x3 images.")
    pipe1, pipe2 = multiprocessing.Pipe()
    tik = time.perf_counter()

    # Create separate processes
    sender_process = multiprocessing.Process(target=send_images,
                                             args=(
                                             camera_ids, pipe1, manager.image_shape, manager.image_dtype, loop_count))
    receiver_process = multiprocessing.Process(target=recv_images,
                                               args=(pipe2, manager.image_shape, manager.image_dtype, loop_count))

    # Start the processes
    sender_process.start()
    receiver_process.start()

    # Wait for the processes to finish
    sender_process.join()
    receiver_process.join()
    pipe_time_elapsed = time.perf_counter() - tik

    print(
        f"PIPE - {loop_count} loops completed in {pipe_time_elapsed:.6f} seconds ({pipe_time_elapsed / loop_count:.6f} seconds per loop, or {1 / (pipe_time_elapsed / loop_count):.2f} loops per second).")

    print(f"Shared memory is {pipe_time_elapsed / shared_memory_time_elapsed:.2f} times faster than pipes.")
    shm.close()
    shm.unlink()
