import time
from typing import List, Tuple, Dict

import cv2
import numpy as np
import pandas as pd


def check_resolution(video_capture: cv2.VideoCapture, width: int, height: int) -> bool:
    return int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)) == width and int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) == height

def check_fourcc(video_capture: cv2.VideoCapture, fourcc: str) -> bool:
    return cv2.VideoWriter_fourcc(*fourcc) == int(video_capture.get(cv2.CAP_PROP_FOURCC))

def measure_latency(video_capture: cv2.VideoCapture) -> Dict[str, float]:
    grab_times = []
    retrieve_times = []
    frame_counts = 0
    start_time = time.perf_counter()

    while frame_counts < 100:
        pre_grab_ns = time.perf_counter_ns()
        video_capture.grab()
        post_grab_ns = time.perf_counter_ns()

        pre_retrieve_ns = time.perf_counter_ns()
        ret, frame = video_capture.retrieve()
        post_retrieve_ns = time.perf_counter_ns()

        if ret:
            grab_times.append((post_grab_ns - pre_grab_ns) / 1e6)  # Convert to milliseconds
            retrieve_times.append((post_retrieve_ns - pre_retrieve_ns) / 1e6) # Convert to milliseconds
            frame_counts += 1

    return {
        'Mean Grab Duration (ms)': np.mean(grab_times),
        'Std Dev Grab Duration (ms)': np.std(grab_times),
        'Mean Retrieve Duration (ms)': np.mean(retrieve_times),
        'Std Dev Retrieve Duration (ms)': np.std(retrieve_times),
        'Mean Frame Rate (fps)': frame_counts / (time.perf_counter() - start_time)
    }

def run_camera_diagnostics(image_sizes: List[Tuple[int, int]], fourcc_codes: List[str]):
    results = []

    for code in fourcc_codes:
        for size in image_sizes:

            print(f"Testing FourCC: {code} at resolution: {size[0]}x{size[1]}")
            video_capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            fourcc = cv2.VideoWriter_fourcc(*code)
            video_capture.set(cv2.CAP_PROP_FOURCC, fourcc)
            video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
            video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])

            success, image = video_capture.read()
            if not success:
                print("Failed to read frame from camera using FourCC: {code} at resolution: {size[0]}x{size[1]}... skipping!")
                continue

            if not image.shape == (size[1], size[0], 3):
                print(f"Image shape mismatch! Expected: {size[1], size[0], 3}, got: {image.shape}... skipping!")
                continue

            latency_metrics = measure_latency(video_capture)
            outcome = {
                'FourCC': code,
                'Resolution': f"{size[0]}x{size[1]}",
                **latency_metrics
            }
            results.append(outcome)
            print(outcome)

            video_capture.release()

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

if __name__ == "__main__":
    image_sizes = [(640, 480), (1280, 720), (1920, 1080)]
    fourcc_codes = ['XVID', 'MJPG', 'X264', 'MP4V', 'H264', 'VP80', 'THEO', 'WMV1', 'WMV2', 'FLV1']

    run_camera_diagnostics(image_sizes, fourcc_codes)