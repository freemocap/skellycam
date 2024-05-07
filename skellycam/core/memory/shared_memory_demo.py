import logging
import multiprocessing
import time

import numpy as np

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def send_images(camera_ids, pipe, image_shape, image_dtype, loop_count):
    test_image = np.random.randint(0, 255, size=image_shape, dtype=image_dtype)
    for i in range(loop_count):
        for camera_id in camera_ids:
            pipe.send(test_image)


def recv_images(pipe, image_shape, image_dtype, loop_count):
    for i in range(loop_count):
        retrieved_image = pipe.recv()


def shared_memory_demo():
    camera_config = CameraConfig()
    camera_ids = [camera_config.camera_id]
    buffer_size = 10 * 1024 * 1024  # 10 MB buffer size
    memory = CameraSharedMemory.from_config(camera_config=camera_config,
                                            buffer_size=buffer_size)
    print(f"Shared memory name: {memory.shared_memory_name}")

    other_memory = CameraSharedMemory.from_config(camera_config=camera_config,
                                                  buffer_size=buffer_size,
                                                  shared_memory_name=memory.shared_memory_name)

    test_image = np.random.randint(0, 255, size=camera_config.image_shape, dtype=np.uint8)
    test_image_kb = test_image.nbytes / 1024
    test_frame = FramePayload.create_dummy(image=test_image)
    for camera_id in camera_ids:
        print(f"Camera{camera_id} - Test image shape: {test_image.shape}")
        print(f"Camera{camera_id} - Test image dtype: {test_image.dtype}")
        index = memory.put_frame(frame=test_frame)
        print(f"Camera{camera_id} - Image index: {index}")
        retrieved_frame = other_memory.get_frame(index=index)
        print(
            f"Camera{camera_id} - Test image shape: {test_image.shape} Retrieved image shape: {retrieved_frame.image_shape}")
        print(
            f"Camera{camera_id} - Test image checksum: {np.sum(test_image)} - Retrieved image checksum: {retrieved_frame.image_checksum}")

    loop_count = 1000
    print(
        f"SHARED MEMORY TEST -  Sending and receiving {loop_count} images (shape: {test_image.shape}, dtype: {test_image.dtype}, size:{test_image_kb}kB).")
    tik = time.perf_counter()
    elapsed_times_ms = []
    for i in range(loop_count):
        tik_loop = time.perf_counter_ns()
        for camera_id in camera_ids:
            index = memory.put_frame(frame=test_frame)
            retrieved_frame = other_memory.get_frame(index=index)
        elapsed_times_ms.append((time.perf_counter_ns() - tik_loop) / 1e6)
    shared_memory_time_elapsed = (time.perf_counter_ns() - tik) / 1e6

    stats = {"total_time": shared_memory_time_elapsed,
             "average_time": np.mean(elapsed_times_ms),
             "std_dev": np.std(elapsed_times_ms),
             "loops_per_second": 1 / np.mean(elapsed_times_ms) * 1e3}
    print("\n\t".join([f"{k}: {v}" for k, v in stats.items()]))

    print("PIPE TEST - Sending and receiving 1000 1920x1080x3 images.")
    pipe1, pipe2 = multiprocessing.Pipe()
    tik = time.perf_counter()

    # Create separate processes
    sender_process = multiprocessing.Process(target=send_images,
                                             args=(
                                                 camera_ids, pipe1, memory.image_shape, memory.image_dtype,
                                                 loop_count))
    receiver_process = multiprocessing.Process(target=recv_images,
                                               args=(pipe2, memory.image_shape, memory.image_dtype, loop_count))

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
    memory.close()
    other_memory.close()

if __name__ == "__main__":
    shared_memory_demo()