import multiprocessing
from multiprocessing import shared_memory
from typing import Tuple

import numpy as np

from skellycam.backend.core.cameras.config.camera_config import CameraConfig, CameraId, CameraConfigs

BUFFER_SIZE = 1024 * 1024 * 1024  # 1 GB


class SharedImageMemoryManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 buffer_size: int = BUFFER_SIZE,
                 existing_shared_memory: shared_memory.SharedMemory = None
                 ):
        self.image_shape = self._calculate_image_shape(camera_configs)
        self.image_dtype = np.uint8
        self.image_size = np.prod(self.image_shape) * np.dtype(self.image_dtype).itemsize  # bytes
        self.buffer_size = buffer_size  # bytes
        self.max_images = buffer_size // self.image_size

        if existing_shared_memory is not None:
            self.shm = existing_shared_memory
        else:
            self.shm = shared_memory.SharedMemory(create=True, size=self.buffer_size)

        self.image_offsets = np.arange(0, self.buffer_size, self.image_size)
        self.next_image_index = 0
        self._lock = multiprocessing.Lock()

    @staticmethod
    def _calculate_image_shape(camera_configs: CameraConfigs) -> Tuple[int, int, int]:
        image_shape = None
        for config in camera_configs.values():
            if image_shape is None:
                # TODO: Support greyscale images
                image_shape = (config.resolution.height, config.resolution.width, 3)
            elif image_shape != config.resolution:
                # TODO: Support different resolutions
                raise ValueError("All camera resolutions must be the same for shared memory.")
        return image_shape

    @property
    def shared_memory_name(self) -> str:
        """
        Returns the name of the shared memory buffer, which can be used to access the buffer from other processes.
        example:
        ```
        manager = SharedImageMemoryManager(image_shape=(480, 640, 3))
        shm = shared_memory.SharedMemory(name=manager.shared_memory_name)
        ```
        """
        return self.shm.name

    def put_image(self, image: np.ndarray) -> int:
        """
        Put an image into the shared memory buffer and return the index at which it was stored.
        """
        with self._lock:
            if image.shape != self.image_shape:
                raise ValueError(f"Iput image shape ({image.shape}) does not match the defined shape for the shared memory ({self.image_shape}).")
            if image.dtype != self.image_dtype:
                raise ValueError(f"Input image dtype ({image.dtype}) does not match the defined dtype for the shared memory ({self.image_dtype}).")
            if self.next_image_index >= self.max_images:
                self.next_image_index = 0

            offset = self.image_offsets[self.next_image_index] * self.image_size
            # Determine the correct size of the slice of the shared memory buffer
            buffer_slice_size = self.image_size
            if offset + buffer_slice_size > self.buffer_size:
                raise ValueError("The offset and buffer slice size exceed the buffer size.")

            shm_array = np.ndarray(self.image_shape,
                                   dtype=self.image_dtype,
                                   buffer=self.shm.buf[offset:offset + buffer_slice_size])
            np.copyto(shm_array, image)

            index = self.next_image_index
            self.next_image_index += 1
            return index

    def get_image(self, index: int) -> np.ndarray:
        """
        Get an image from the shared memory buffer using the specified index.
        """
        with self._lock:
            offset = self.image_offsets[index] * self.image_size
            # Create a NumPy array from the shared memory buffer
            image_shared = np.ndarray(self.image_shape, dtype=self.image_dtype,
                                      buffer=self.shm.buf[offset:offset + self.image_size])

            return image_shared.copy()  # Return a copy of the image not a reference

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()


if __name__ == "__main__":

    manager = SharedImageMemoryManager(camera_configs={CameraId(0): CameraConfig()})
    print(f"Shared memory name: {manager.shared_memory_name}")
    shm = shared_memory.SharedMemory(name=manager.shared_memory_name)
    print(f"Shared memory size: {shm.size}")
    test_image = np.random.randint(0, 255, size=manager.image_shape, dtype=manager.image_dtype)
    print(f"Test image shape: {test_image.shape}")
    print(f"Test image dtype: {test_image.dtype}")
    index = manager.put_image(test_image)
    print(f"Image index: {index}")
    retrieved_image = manager.get_image(index)
    print(f"Retrieved image shape: {retrieved_image.shape}")
    print(f"Retrieved image dtype: {retrieved_image.dtype}")
    print(f"Images are equal: {np.array_equal(test_image, retrieved_image)}")