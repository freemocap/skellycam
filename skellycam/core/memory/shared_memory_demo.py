import logging
import multiprocessing
from multiprocessing import shared_memory

import numpy as np

from skellycam.core.detection.camera_id import CameraId
from skellycam.core.detection.video_resolution import VideoResolution
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

logger = logging.getLogger(__name__)
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
    manager = CameraSharedMemoryManager(
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
