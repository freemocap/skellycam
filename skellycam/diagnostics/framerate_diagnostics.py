import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
from pydantic import BaseModel
from rich import print
from scipy.stats import median_abs_deviation

from skellycam.detection.detect_cameras import detect_cameras
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


class TimestampDiagnosticsDataClass(BaseModel):
    mean_framerates_per_camera: dict
    standard_deviation_framerates_per_camera: dict
    median_framerates_per_camera: dict
    median_absolute_deviation_per_camera: dict
    mean_mean_framerate: float
    mean_standard_deviation_framerates: float
    mean_median_framerates: float
    mean_median_absolute_deviation_per_camera: float


def gather_timestamps(list_of_frames: List[FramePayload]) -> np.ndarray:
    timestamps_npy = np.empty(0)

    for frame in list_of_frames:
        timestamps_npy = np.append(timestamps_npy, frame.timestamp_ns)
    return timestamps_npy


def create_timestamp_diagnostic_plots(
    raw_frame_list_dictionary: Dict[str, List[FramePayload]],
    synchronized_frame_list_dictionary: Dict[str, List[FramePayload]],
    path_to_save_plots_png: Union[str, Path],
    open_image_after_saving: bool = False,
):
    """plot some diagnostics to assess quality of camera sync"""

    # opportunistic load of matplotlib to avoid startup time costs
    from matplotlib import pyplot as plt

    plt.set_loglevel("warning")

    synchronized_timestamps_dictionary = {}
    for (
        camera_id,
        camera_synchronized_frame_list,
    ) in synchronized_frame_list_dictionary.items():
        synchronized_timestamps_dictionary[camera_id] = (
            gather_timestamps(camera_synchronized_frame_list) / 1e9
        )

    raw_timestamps_dictionary = {}
    for camera_id, camera_raw_frame_list in raw_frame_list_dictionary.items():
        raw_timestamps_dictionary[camera_id] = (
            gather_timestamps(camera_raw_frame_list) / 1e9
        )

    max_frame_duration = 0.1
    fig = plt.figure(figsize=(18, 10))
    ax1 = plt.subplot(
        231,
        title="(Raw) Camera Frame Timestamp vs Frame#",
        xlabel="Frame#",
        ylabel="Timestamp (sec)",
    )
    ax2 = plt.subplot(
        232,
        ylim=(0, max_frame_duration),
        title="(Raw) Camera Frame Duration Trace",
        xlabel="Frame#",
        ylabel="Duration (sec)",
    )
    ax3 = plt.subplot(
        233,
        xlim=(0, max_frame_duration),
        title="(Raw) Camera Frame Duration Histogram (count)",
        xlabel="Duration(s, 1ms bins)",
        ylabel="Probability",
    )
    ax4 = plt.subplot(
        234,
        title="(Synchronized) Camera Frame Timestamp vs Frame#",
        xlabel="Frame#",
        ylabel="Timestamp (sec)",
    )
    ax5 = plt.subplot(
        235,
        ylim=(0, max_frame_duration),
        title="(Synchronized) Camera Frame Duration Trace",
        xlabel="Frame#",
        ylabel="Duration (sec)",
    )
    ax6 = plt.subplot(
        236,
        xlim=(0, max_frame_duration),
        title="(Synchronized) Camera Frame Duration Histogram (count)",
        xlabel="Duration(s, 1ms bins)",
        ylabel="Probability",
    )

    for camera_id, timestamps in raw_timestamps_dictionary.items():
        ax1.plot(timestamps, label=f"Camera# {str(camera_id)}")
        ax1.legend()
        ax2.plot(np.diff(timestamps), ".")
        ax3.hist(
            np.diff(timestamps),
            bins=np.arange(0, max_frame_duration, 0.0025),
            alpha=0.5,
        )

    for camera_id, timestamps in synchronized_timestamps_dictionary.items():
        ax4.plot(timestamps, label=f"Camera# {str(camera_id)}")
        ax4.legend()
        ax5.plot(np.diff(timestamps), ".")
        ax6.hist(
            np.diff(timestamps),
            bins=np.arange(0, max_frame_duration, 0.0025),
            alpha=0.5,
        )

    fig_save_path = Path(path_to_save_plots_png)
    plt.savefig(str(fig_save_path))
    logger.info(f"Saving diagnostic figure as png")

    if open_image_after_saving:
        os.startfile(path_to_save_plots_png, "open")


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
