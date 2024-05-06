import multiprocessing
from multiprocessing import shared_memory
from typing import Tuple

import numpy as np

from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.device_detection.video_resolution import VideoResolution

BUFFER_SIZE = 1024 * 1024 * 1024  # 1 GB


class SharedImageMemoryManager:
    def __init__(self,
                 image_resolution: VideoResolution,
                 color_channels: int = 3,
                 image_dtype: np.dtype = np.uint8,
                 buffer_size: int = BUFFER_SIZE,
                 existing_shared_memory: shared_memory.SharedMemory = None
                 ):
        self.image_shape = (image_resolution.height, image_resolution.width, color_channels)
        self.image_dtype = image_dtype
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

    def put_image(self, image: np.ndarray) -> int:
        """
        Put an image into the shared memory buffer and return the index at which it was stored.
        """
        with self._lock:
            if image.shape != self.image_shape:
                raise ValueError(
                    f"Iput image shape ({image.shape}) does not match the defined shape for the shared memory ({self.image_shape}).")
            if image.dtype != self.image_dtype:
                raise ValueError(
                    f"Input image dtype ({image.dtype}) does not match the defined dtype for the shared memory ({self.image_dtype}).")
            if self.next_image_index >= self.max_images:
                self.next_image_index = 0

            offset = self.image_offsets[self.next_image_index]
            # Determine the correct size of the slice of the shared memory buffer
            buffer_slice_size = self.image_size
            if offset + buffer_slice_size > self.buffer_size:
                raise ValueError(
                    f"Offset {offset} + buffer slice size {buffer_slice_size} exceeds buffer size {self.buffer_size}.")

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
            offset = self.image_offsets[index]
            # Create a NumPy array from the shared memory buffer
            image_shared = np.ndarray(self.image_shape, dtype=self.image_dtype,
                                      buffer=self.shm.buf[offset:offset + self.image_size])

            return image_shared.copy()  # Return a copy of the image not a reference

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()

## uncomment the following code and run this file as a script to test the shared memory manager relative to pipes
#
# def send_images(pipe, image_shape, image_dtype, loop_count):
#     test_image = np.random.randint(0, 255, size=image_shape, dtype=image_dtype)
#     for i in range(loop_count):
#         pipe.send(test_image)
#
#
#
# def recv_images(pipe, image_shape, image_dtype, loop_count):
#     for i in range(loop_count):
#         retrieved_image = pipe.recv()
#
# if __name__ == "__main__":
#
#     manager = SharedImageMemoryManager(camera_configs={CameraId(0): CameraConfig()})
#     print(f"Shared memory name: {manager.shared_memory_name}")
#     shm = shared_memory.SharedMemory(name=manager.shared_memory_name)
#     print(f"Shared memory size: {shm.size}")
#     test_image = np.random.randint(0, 255, size=manager.image_shape, dtype=manager.image_dtype)
#     print(f"Test image shape: {test_image.shape}")
#     print(f"Test image dtype: {test_image.dtype}")
#     index = manager.put_image(test_image)
#     print(f"Image index: {index}")
#     retrieved_image = manager.get_image(index)
#     print(f"Retrieved image shape: {retrieved_image.shape}")
#     print(f"Retrieved image dtype: {retrieved_image.dtype}")
#     print(f"Images are equal: {np.array_equal(test_image, retrieved_image)}")
#
#     loop_count = 1000
#     print("SHARED MEMORY TEST -  Sending and receiving 1000 1920x1080x3 images.")
#     tik = time.perf_counter()
#     test_image = np.random.randint(0, 255, size=manager.image_shape, dtype=manager.image_dtype)
#     for i in range(loop_count):
#         index = manager.put_image(test_image)
#         retrieved_image = manager.get_image(index)
#     shared_memory_time_elapsed = time.perf_counter() - tik
#     print(f"SHARED MEMORY - {loop_count} loops completed in {shared_memory_time_elapsed:.6f} seconds ({shared_memory_time_elapsed / loop_count:.6f} seconds per loop, or {1 / (shared_memory_time_elapsed / loop_count):.2f} loops per second).")
#
#
#
#
#     print("PIPE TEST - Sending and receiving 1000 1920x1080x3 images.")
#     pipe1, pipe2 = multiprocessing.Pipe()
#     tik = time.perf_counter()
#
#     # Create separate processes
#     sender_process = multiprocessing.Process(target=send_images,
#                                              args=(pipe1, manager.image_shape, manager.image_dtype, loop_count))
#     receiver_process = multiprocessing.Process(target=recv_images,
#                                                args=(pipe2, manager.image_shape, manager.image_dtype, loop_count))
#
#     # Start the processes
#     sender_process.start()
#     receiver_process.start()
#
#     # Wait for the processes to finish
#     sender_process.join()
#     receiver_process.join()
#     pipe_time_elapsed = time.perf_counter() - tik
#
#     print(f"PIPE - {loop_count} loops completed in {pipe_time_elapsed:.6f} seconds ({pipe_time_elapsed / loop_count:.6f} seconds per loop, or {1 / (pipe_time_elapsed / loop_count):.2f} loops per second).")
#
#     print(f"Shared memory is {pipe_time_elapsed / shared_memory_time_elapsed:.2f} times faster than pipes.")
#     shm.close()
#     shm.unlink()
