import logging
import time

import numpy as np

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def shared_memory_demo():
    camera_config = CameraConfig()
    # camera_config.resolution = ImageResolution(width=1280, height=720) #try different resolutions
    camera_ids = [camera_config.camera_id]
    buffer_size = 1024 * 1024 * 1024  # 1 GB buffer size for all cameras
    memory = CameraSharedMemory.from_config(camera_config=camera_config,
                                            buffer_size=buffer_size)
    print(f"Shared memory name: {memory.shared_memory_name}")

    other_memory = CameraSharedMemory.from_config(camera_config=camera_config,
                                                  buffer_size=buffer_size,
                                                  shared_memory_name=memory.shared_memory_name)

    test_image = np.random.randint(0, 255, size=camera_config.image_shape, dtype=np.uint8)
    test_image_kb = test_image.nbytes / 1024
    test_frame = FramePayload.create_dummy(image=test_image)
    for _ in range(4):
        for camera_id in camera_ids:
            print(f"Camera{camera_id} - Test image shape: {test_image.shape}")
            print(f"Camera{camera_id} - Test image dtype: {test_image.dtype}")
            index = memory.put_frame(frame=test_frame)
            print(f"Camera{camera_id} - Image index: {index}")
            retrieved_frame = other_memory.retrieve_frame(index=index)
            print(
                f"Camera{camera_id} - Test image shape: {test_image.shape} Retrieved image shape: {retrieved_frame.image_shape}")
            print(
                f"Camera{camera_id} - Test image checksum: {np.sum(test_image)} - Retrieved image checksum: {retrieved_frame.image_checksum}")

    loop_count = 800
    print(
        f"SHARED MEMORY TEST -  Sending and receiving {loop_count} images (shape: {test_image.shape}, dtype: {test_image.dtype}, size:{test_image_kb}kB).")
    tik = time.perf_counter_ns()
    elapsed_times_ms = []
    elapsed_put_times_ms = []
    elapsed_get_times_ms = []
    for loop in range(loop_count):
        if loop % 100 == 0:
            print(f"Loop {loop} of {loop_count}")
        tik_loop = time.perf_counter_ns()
        for camera_id in camera_ids:
            tik_before_put = time.perf_counter_ns()
            index = memory.put_frame(frame=test_frame)
            elapsed_put_times_ms.append((time.perf_counter_ns() - tik_before_put) / 1e6)
            tik_before_get = time.perf_counter_ns()
            test_frame = other_memory.retrieve_frame(index=index)
            elapsed_get_times_ms.append((time.perf_counter_ns() - tik_before_get) / 1e6)
        elapsed_times_ms.append((time.perf_counter_ns() - tik_loop) / 1e6)

    shared_memory_time_elapsed_s = (time.perf_counter_ns() - tik) / 1e9

    stats = {"total_time (sec)": shared_memory_time_elapsed_s,
             "average_time_per_put(ms)": np.mean(elapsed_put_times_ms),
             "average_time_per_get(ms)": np.mean(elapsed_get_times_ms),
             "average_time_per_loop(ms)": np.mean(elapsed_times_ms),
             "std_dev(ms)": np.std(elapsed_times_ms),
             "loops_per_second": 1 / np.mean(elapsed_times_ms) * 1e3}
    print("\n\t".join([f"{k}: {v}" for k, v in stats.items()]))


if __name__ == "__main__":
    shared_memory_demo()
