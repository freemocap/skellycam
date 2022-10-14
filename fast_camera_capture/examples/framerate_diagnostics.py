import time

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from scipy.stats import median_abs_deviation
from rich import print

matplotlib.use("qt5agg")
matplotlib.set_loglevel("warning")

from fast_camera_capture.opencv.group.camera_group import CameraGroup


def show_timestamp_diagnostic_plots(timestamps_dictionary: dict, shared_zero_time: int):
    # plot timestamps
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 10))
    max_frame_duration = .1 #sec

    ax2.plot([0, 100], [.033, .033], 'k-', label="30 fps")
    ax3.plot([.033, .033], [0, 100], 'k-', label="30 fps")

    for cam_id, timestamps in timestamps_dictionary.items():
        timestamps_formatted = np.asarray(timestamps) - shared_zero_time
        timestamps_formatted = timestamps_formatted / 1e9

        ax1.plot(timestamps_formatted,'.-', label=cam_id)
        ax1.set_xlabel("Frame number")
        ax1.set_ylabel("Timestamp (sec)")
        ax1.set_title("Timestamps from shared zero")
        ax1.legend()

        ax2.plot(np.diff(timestamps_formatted), '.', label=cam_id, alpha=.5)
        ax2.set_ylim(0, max_frame_duration)
        ax2.set_xlabel("Frame number")
        ax2.set_ylabel("Frame duration (sec)")
        ax2.set_title("Frame Duration (time elapsed between timestamps)")
        ax2.legend()

        ax3.hist(np.diff(timestamps_formatted),
                 bins=np.arange(0, max_frame_duration, .001),
                 label=cam_id,
                 alpha=0.5,
                 density=True)

        ax3.set_xlabel("Frame duration (sec)")
        ax3.set_ylabel("Number of frames with a given duration")
        ax3.set_title("Histogram of frame durations")
        ax3.legend()

    plt.show()


def calculate_camera_diagnostic_results(timestamps_dictionary)->dict:
    mean_framerates_per_camera = {}
    standard_deviation_framerates_per_camera = {}
    median_framerates_per_camera = {}
    median_absolute_deviation_per_camera = {}
    for cam_id, timestamps in timestamps_dictionary.items():
        timestamps_formatted = (np.asarray(timestamps) - timestamps[0]) / 1e9
        frame_durations = np.diff(timestamps_formatted)
        framerate_per_frame = 1 / frame_durations
        mean_framerates_per_camera[cam_id] = np.nanmean(framerate_per_frame)
        median_framerates_per_camera[cam_id] = np.nanmedian(framerate_per_frame)
        standard_deviation_framerates_per_camera[cam_id] = np.nanstd(framerate_per_frame)
        median_absolute_deviation_per_camera[cam_id] = median_abs_deviation(framerate_per_frame)

    mean_mean_framerate = np.nanmean(list(mean_framerates_per_camera.values()))
    mean_standard_deviation_framerates = np.nanmean(list(standard_deviation_framerates_per_camera.values()))
    mean_median_framerates = np.nanmean(list(median_framerates_per_camera.values()))
    mean_median_absolute_deviation_per_camera = np.nanmean(list(median_absolute_deviation_per_camera.values()))

    return {"mean_framerates_per_camera": mean_framerates_per_camera,
            "standard_deviation_framerates_per_camera": standard_deviation_framerates_per_camera,
            "median_framerates_per_camera": median_framerates_per_camera,
            "median_absolute_deviation_per_camera": median_absolute_deviation_per_camera,
            "mean_mean_framerate": mean_mean_framerate,
            "mean_standard_deviation_framerates": mean_standard_deviation_framerates,
            "mean_median_framerates": mean_median_framerates,
            "mean_median_absolute_deviation_per_camera": mean_median_absolute_deviation_per_camera}




if __name__ == "__main__":
    cam_ids = ["0", "1", "2", "3", "4", "5", "6"]
    # cam_ids = ["0"]
    g = CameraGroup(cam_ids)
    g.start()

    timestamps_dictionary = {key: [] for key in cam_ids}

    loop_time = time.perf_counter_ns()

    break_after_n_frames = 200
    shared_zero_time = time.perf_counter_ns()
    while True:
        prev_loop_time = loop_time
        loop_time = time.perf_counter_ns()
        loop_duration = (loop_time - prev_loop_time) / 1e6

        for cam_id in cam_ids:
            frame_payload = g.get_by_cam_id(cam_id)
            if frame_payload is not None:
                if frame_payload.success:
                    timestamps_dictionary[cam_id].append(frame_payload.timestamp_ns)

        print(
            f"Loop duration: {loop_duration:.3f} ms: Timestamps: {[len(val) for val in timestamps_dictionary.values()]}")

        if len(timestamps_dictionary[cam_id]) > break_after_n_frames:
            break

    timestamp_diagnostic_results_dict = calculate_camera_diagnostic_results(timestamps_dictionary)
    print(timestamp_diagnostic_results_dict)
    show_timestamp_diagnostic_plots(timestamps_dictionary, shared_zero_time)
