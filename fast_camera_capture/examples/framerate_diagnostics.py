import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import median_abs_deviation
from rich import print

from fast_camera_capture.detection.detect_cameras import detect_cameras

from fast_camera_capture.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


@dataclass
class TimestampDiagnosticsDataClass:
    mean_framerates_per_camera: dict
    standard_deviation_framerates_per_camera: dict
    median_framerates_per_camera: dict
    median_absolute_deviation_per_camera: dict
    mean_mean_framerate: float
    mean_standard_deviation_framerates: float
    mean_median_framerates: float
    mean_median_absolute_deviation_per_camera: float


def show_timestamp_diagnostic_plots(
    timestamps_dictionary: dict,
    shared_zero_time: int,
    save_path: str | Path,
    show_plot: bool = False,
):
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.use("qt5agg")
    matplotlib.set_loglevel("warning")
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12, 4))

    # plot timestamps
    max_frame_duration = 0.1  # sec

    ax1.set_xlabel("Frame number")
    ax1.set_ylabel("Timestamp (sec)")
    ax1.set_title("Timestamps from shared zero")

    ax2.set_ylim(0, max_frame_duration)
    ax2.set_xlabel("Frame number")
    ax2.set_ylabel("Frame duration (sec)")
    ax2.set_title("Frame Duration (time elapsed between timestamps)")

    ax3.set_xlabel("Frame duration (sec)")
    ax3.set_ylabel("Number of frames with a given duration")
    ax3.set_title("Histogram of frame durations")

    number_of_frames = len(list(timestamps_dictionary.values())[0])
    ax2.plot([0, number_of_frames], [0.033, 0.033], "k-", label="30 fps")
    ax3.plot([0.033, 0.033], [0, number_of_frames], "k-", label="30 fps")

    for cam_id, timestamps in timestamps_dictionary.items():
        timestamps_formatted = np.asarray(timestamps) - shared_zero_time
        timestamps_formatted = timestamps_formatted / 1e9

        ax1.plot(timestamps_formatted, ".-", label=cam_id)
        ax1.legend()

        ax2.plot(np.diff(timestamps_formatted), ".", label=cam_id, alpha=0.5)

        ax2.legend()

        ax3.hist(
            np.diff(timestamps_formatted),
            bins=np.arange(0, max_frame_duration, 0.001),
            label=cam_id,
            alpha=0.5,
            density=True,
        )
        ax3.legend()

    plt.tight_layout()
    figure_file_path = Path(save_path) / "timestamp_diagnostics.png"
    plt.savefig(figure_file_path)
    logger.info(f"Saved timestamp diagnostic plot to {figure_file_path}")
    if show_plot:
        plt.show()
        plt.pause(0.1)
        input("Press Enter to continue...")
        plt.close()


def calculate_camera_diagnostic_results(
    timestamps_dictionary,
) -> TimestampDiagnosticsDataClass:
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
        standard_deviation_framerates_per_camera[cam_id] = np.nanstd(
            framerate_per_frame
        )
        median_absolute_deviation_per_camera[cam_id] = median_abs_deviation(
            framerate_per_frame
        )

    mean_mean_framerate = np.nanmean(list(mean_framerates_per_camera.values()))
    mean_standard_deviation_framerates = np.nanmean(
        list(standard_deviation_framerates_per_camera.values())
    )
    mean_median_framerates = np.nanmean(list(median_framerates_per_camera.values()))
    mean_median_absolute_deviation_per_camera = np.nanmean(
        list(median_absolute_deviation_per_camera.values())
    )

    return TimestampDiagnosticsDataClass(
        mean_framerates_per_camera=mean_framerates_per_camera,
        standard_deviation_framerates_per_camera=standard_deviation_framerates_per_camera,
        median_framerates_per_camera=median_framerates_per_camera,
        median_absolute_deviation_per_camera=median_absolute_deviation_per_camera,
        mean_mean_framerate=float(mean_mean_framerate),
        mean_standard_deviation_framerates=float(mean_standard_deviation_framerates),
        mean_median_framerates=float(mean_median_framerates),
        mean_median_absolute_deviation_per_camera=float(
            mean_median_absolute_deviation_per_camera
        ),
    )


if __name__ == "__main__":
    found_camera_response = detect_cameras()
    cam_ids = found_camera_response.cameras_found_list
    g = CameraGroup(cam_ids)
    g.start()

    timestamps_dictionary_in = {key: [] for key in cam_ids}

    loop_time = time.perf_counter_ns()

    break_after_n_frames = 200
    shared_zero_time_in = time.perf_counter_ns()
    should_continue = True
    while should_continue:
        prev_loop_time = loop_time
        loop_time = time.perf_counter_ns()
        loop_duration = (loop_time - prev_loop_time) / 1e6

        for cam_id in cam_ids:
            frame_payload = g.get_by_cam_id(cam_id)
            if frame_payload is not None:
                if frame_payload.success:
                    timestamps_dictionary_in[cam_id].append(frame_payload.timestamp_ns)
            if len(timestamps_dictionary_in[cam_id]) > break_after_n_frames:
                should_continue = False

        print(
            f"Loop duration: {loop_duration:.3f} ms: Timestamps: {[len(val) for val in timestamps_dictionary_in.values()]}"
        )

    timestamp_diagnostic_data_class = calculate_camera_diagnostic_results(
        timestamps_dictionary_in
    )
    print(timestamp_diagnostic_data_class.__dict__)
    show_timestamp_diagnostic_plots(
        timestamps_dictionary_in, shared_zero_time_in, pause_on_show=True
    )
