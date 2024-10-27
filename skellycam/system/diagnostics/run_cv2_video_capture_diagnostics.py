import time
from typing import List, Tuple, Dict

import cv2
import numpy as np
import pandas as pd

from skellycam.core.camera_group.camera.opencv.determine_backend import BackendSelection


def check_resolution(video_capture: cv2.VideoCapture, width: int, height: int) -> bool:
    return int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)) == width and int(
        video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) == height


def check_fourcc(video_capture: cv2.VideoCapture, fourcc: str) -> bool:
    return cv2.VideoWriter_fourcc(*fourcc) == int(video_capture.get(cv2.CAP_PROP_FOURCC))


def measure_latency(video_capture: cv2.VideoCapture, max_frame_count: int = 30) -> Dict[str, float]:
    grab_times = []
    retrieve_times = []
    frame_counts = 0
    start_time = time.perf_counter()

    while frame_counts < max_frame_count:
        pre_grab_ns = time.perf_counter_ns()
        video_capture.grab()
        post_grab_ns = time.perf_counter_ns()

        pre_retrieve_ns = time.perf_counter_ns()
        ret, frame = video_capture.retrieve()
        post_retrieve_ns = time.perf_counter_ns()

        if ret:
            grab_times.append((post_grab_ns - pre_grab_ns) / 1e6)  # Convert to milliseconds
            retrieve_times.append((post_retrieve_ns - pre_retrieve_ns) / 1e6)  # Convert to milliseconds
            frame_counts += 1
        else:
            grab_times.append(np.nan)  # Convert to milliseconds
            retrieve_times.append(np.nan)  # Convert to milliseconds
            frame_counts += 1

    return {
        'Mean Frame Rate (fps)': frame_counts / (time.perf_counter() - start_time),
        'Mean Grab Duration (ms)': np.nanmean(grab_times),
        'Std Dev Grab Duration (ms)': np.nanstd(grab_times),
        'Mean Retrieve Duration (ms)': np.nanmean(retrieve_times),
        'Std Dev Retrieve Duration (ms)': np.nanstd(retrieve_times),
    }


def run_camera_diagnostics(image_sizes: List[Tuple[int, int]], fourcc_codes: List[str]):
    results = []
    try:
        for backend in BackendSelection:
            if backend.value not in [cv2.CAP_DSHOW, cv2.CAP_V4L, cv2.CAP_V4L2, cv2.CAP_ANY, cv2.CAP_FFMPEG, cv2.CAP_OPENCV_MJPEG]:
                continue
            for code in fourcc_codes:
                for size in image_sizes:
                    print(f"Testing backend {backend.name}: FourCC: {code} at resolution: {size[0]}x{size[1]}")
                    video_capture = cv2.VideoCapture(0, backend.value)
                    outcome = "init-outcome"
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*code)
                        video_capture.set(cv2.CAP_PROP_FOURCC, fourcc)

                        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
                        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
                        success, image = video_capture.read()
                        if not success:
                            print(
                                f"Failed to read frame from camera using backend: {backend.name},  FourCC: {code} at resolution: {size[0]}x{size[1]}...")
                        #     continue
                        #
                        # if not image.shape == (size[1], size[0], 3):
                        #     print(f"Image shape mismatch! Expected: {size[1], size[0], 3}, got: {image.shape}... skipping!")
                        #     continue

                        latency_metrics = measure_latency(video_capture)
                        outcome = {
                            'Backend': backend.name,
                            'FourCC': code,
                            'Resolution': f"{size[0]}x{size[1]}",
                            **latency_metrics
                        }
                        results.append(outcome)
                    except Exception as e:
                        print(
                            f"Failed to read frame from camera using backend: {backend.name},  FourCC: {code} at resolution: {size[0]}x{size[1]}...")
                    finally:
                        video_capture.release()
                        print(f"\n{outcome}\n")


    except Exception as e:
        print(
        f"Failed to read frame from camera using backend: {backend.name},  FourCC: {code} at resolution: {size[0]}x{size[1]}...")
    finally:

        df = pd.DataFrame(results)
        pd.set_option('display.float_format', '{:.3f}'.format)
        print(df.to_string(index=False))


if __name__ == "__main__":
    image_sizes = [(640, 480) , (1280, 720), (1920, 1080)]
    fourcc_codes = ['XVID', 'MJPG', 'X264', 'MP4V', 'H264',]

    run_camera_diagnostics(image_sizes, fourcc_codes)
