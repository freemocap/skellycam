import logging
import multiprocessing
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
    lock = multiprocessing.Lock()
    memory = CameraSharedMemory.from_config(camera_config=camera_config,
                                            lock=lock)

    print(f"Shared memory name: {memory.shared_memory_name}")

    other_memory = CameraSharedMemory.from_config(camera_config=camera_config,
                                                  lock=lock,
                                                  shared_memory_name=memory.shared_memory_name)

    test_image = np.random.randint(0, 255, size=camera_config.image_shape, dtype=np.uint8)
    test_image_kb = test_image.nbytes / 1024
    test_frame = FramePayload.create_dummy()
    for _ in range(4):
        for camera_id in camera_ids:
            print(f"Camera{camera_id} - Test image shape: {test_image.shape}")
            print(f"Camera{camera_id} - Test image dtype: {test_image.dtype}")
            memory.put_frame(frame=test_frame,
                             image=test_image)
            print(f"Camera{camera_id} - Test frame written to shared memory at index {memory.last_frame_written_index}")
            retrieved_frame = other_memory.get_next_frame()
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
            index = memory.put_frame(frame=test_frame, image=test_image)
            elapsed_put_times_ms.append((time.perf_counter_ns() - tik_before_put) / 1e6)
            tik_before_get = time.perf_counter_ns()
            test_frame = other_memory.get_next_frame()
            elapsed_get_times_ms.append((time.perf_counter_ns() - tik_before_get) / 1e6)
        elapsed_times_ms.append((time.perf_counter_ns() - tik_loop) / 1e6)

    shared_memory_time_elapsed_s = (time.perf_counter_ns() - tik) / 1e9

    stats = {"total_time (sec)": shared_memory_time_elapsed_s,
             "time_per_put(ms)": f"mean:{np.mean(elapsed_put_times_ms):.3f}, median:{np.median(elapsed_put_times_ms):.3f}, std:{np.std(elapsed_put_times_ms):.3f}",
             "time_per_get(ms)": f"mean:{np.mean(elapsed_get_times_ms):.3f}, median:{np.median(elapsed_get_times_ms):.3f}, std:{np.std(elapsed_get_times_ms):.3f}",
             "time_per_loop(ms)": f"mean:{np.mean(elapsed_times_ms):.3f}, median:{np.median(elapsed_times_ms):.3f}, std:{np.std(elapsed_times_ms):.3f}",
             "loops_per_second": f"mean: {loop_count / shared_memory_time_elapsed_s:.3f}, median: {loop_count / np.median(elapsed_times_ms):.3f}, std: {loop_count / np.std(elapsed_times_ms):.3f}"}

    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    shared_memory_demo()
