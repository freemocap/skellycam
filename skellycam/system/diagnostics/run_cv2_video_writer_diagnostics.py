import time
from typing import List, Tuple

import cv2
import numpy as np
import pandas as pd


def get_file_extension(fourcc: str) -> str:
    if fourcc in ['XVID', 'MJPG']:
        return 'avi'
    elif fourcc in ['X264', 'H264']:
        return 'mp4'
    elif fourcc in ['MP4V']:
        return 'mp4'
    elif fourcc in ['VP80', 'VP90']:
        return 'webm'
    elif fourcc in ['WMV1', 'WMV2', 'WMV3']:
        return 'wmv'
    elif fourcc in ['DIVX']:
        return 'avi'
    elif fourcc in ['HEVC']:
        return 'mp4'
    elif fourcc in ['AVC1']:
        return 'mp4'
    elif fourcc in ['FLV1']:
        return 'flv'
    else:
        return 'avi'


def measure_write_time(image_size: Tuple[int, int],
                       fourcc: str,
                       num_frames: int = 30,
                       randomize: bool = True) -> List[float]:
    width, height = image_size
    file_extension = get_file_extension(fourcc)
    if randomize:
        filename = f'temp_video-{fourcc}-random.{file_extension}'
    else:
        filename = f'temp_video-{fourcc}-fixed.{file_extension}'
    video_writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*fourcc), 30, (width, height))

    frame = (255 * np.random.rand(height, width, 3)).astype('uint8')
    times = []

    if randomize:
        frames = [(255 * np.random.rand(height, width, 3)).astype('uint8') for _ in range(num_frames)]
    else:
        frames = [frame] * num_frames

    for _ in range(num_frames):
        start_time = time.perf_counter_ns()
        video_writer.write(frame)
        end_time = time.perf_counter_ns()
        times.append((end_time - start_time) / 1e6)  # Convert to milliseconds

    video_writer.release()
    cv2.destroyAllWindows()

    return times


def run_cv2_video_writer_diagnostics(image_sizes: List[Tuple[int, int]], fourcc_codes: List[str]):
    results = []

    for size in image_sizes:
        for code in fourcc_codes:
            for randomize in [True, False]:
                times = measure_write_time(size, code, randomize=randomize)
                mean_time = np.mean(times)
                std_time = np.std(times)
                outcome = {
                    'FourCC': code,
                    'Image Size': f"{size[0]}x{size[1]}",
                    'Randomize': randomize,
                    'Mean Frame Write Time (ms)': mean_time,
                    'Std Dev Frame Write Time (ms)': std_time
                }
                results.append(outcome)
                print(outcome)

    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    print("\nGrouped by FourCC")

    grouped = df.groupby('FourCC')

    summary_results = []

    for name, group in grouped:
        group_mean = group['Mean Frame Write Time (ms)'].mean()
        group_std = group['Mean Frame Write Time (ms)'].std()
        summary_results.append({
            'FourCC': name,
            'Overall Mean Write Time (ms)': group_mean,
            'Overall Std Dev Write Time (ms)': group_std
        })
        print(f"FourCC: {name}")
        print(group.to_string(index=False))
        print(
            f"\nMean values for FourCC {name}:\n{group[['Mean Frame Write Time (ms)', 'Std Dev Frame Write Time (ms)']].mean()}")
        print("\n")

    summary_df = pd.DataFrame(summary_results)
    print("\nSummary of Mean and Std Dev Write Times by FourCC")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    image_sizes = [(640, 480), (1280, 720), (1920, 1080)]
    fourcc_codes = ['XVID', 'MJPG', 'X264', 'MP4V', 'H264', 'VP80', 'THEO', 'WMV1', 'WMV2', 'FLV1']

    run_cv2_video_writer_diagnostics(image_sizes, fourcc_codes)
