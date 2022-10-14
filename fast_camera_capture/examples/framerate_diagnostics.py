import time

import numpy as np
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("qt5agg")

from fast_camera_capture.opencv.group.camera_group import CameraGroup


def show_timestamp_diagnostic_plots(timestamps_dictionary: dict, shared_zero_time: int):
    # plot timestamps
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 10))
    max_frame_duration = 100 #ms
    for cam_id, timestamps in timestamps_dictionary.items():
        timestamps_formatted = np.asarray(timestamps) - shared_zero_time
        timestamps_formatted = timestamps_formatted / 1e6

        ax1.plot(timestamps_formatted,'.-', label=cam_id)
        ax1.set_xlabel("Frame number")
        ax1.set_ylabel("Timestamp (msec)")
        ax1.set_title("Timestamps from shared zero")
        ax1.legend()

        ax2.plot(np.diff(timestamps_formatted), '.-', label=cam_id)
        ax2.set_xlabel("Frame number")
        ax2.set_ylabel("Frame duration (msec)")
        ax2.set_title("Frame Duration (time elapsed between timestamps)")
        ax2.legend()

        ax3.hist(np.diff(timestamps_formatted),
                 bins=np.arange(0, max_frame_duration, 1),
                 label=cam_id,
                 alpha=0.5,
                 density=True)
        ax3.set_xlabel("Frame duration (ms)")
        ax3.set_ylabel("Proportion of frames with a given duration")
        ax3.set_title("Histogram of frame durations")
        ax3.legend()

    plt.show()


if __name__ == "__main__":
    # cam_ids = ["0", "1", "2", "3", "4", "5", "6"]
    cam_ids = ["0"]
    g = CameraGroup(cam_ids)
    g.start()

    timestamps_dictionary = {key: [] for key in cam_ids}

    loop_time = time.perf_counter_ns()

    break_after_n_frames = 100
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
            f"Loop duration: {loop_duration:.3} ms: Timestamps: {[len(val) for val in timestamps_dictionary.values()]}")

        if len(timestamps_dictionary[cam_id]) > break_after_n_frames:
            break

    show_timestamp_diagnostic_plots(timestamps_dictionary, shared_zero_time)
