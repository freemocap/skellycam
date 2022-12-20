import logging
from pathlib import Path
from pprint import pprint
from typing import Dict, Union

from skellycam.diagnostics.framerate_diagnostics import (
    calculate_camera_diagnostic_results,
    create_timestamp_diagnostic_plots,
)
from skellycam.diagnostics.plot_first_and_last_frames import plot_first_and_last_frames
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


def create_diagnostic_plots(
    video_recorder_dictionary: Dict[str, VideoRecorder],
    synchronized_frame_list_dictionary: Dict[str, list],
    folder_to_save_plots: Union[str, Path],
    shared_zero_time: Union[int, float] = 0,
    show_plots_bool: bool = True,
):
    logger.info("Creating diagnostic plots...")
    # get timestamp diagnostics
    timestamps_dictionary = {}
    for cam_id, video_recorder in video_recorder_dictionary.items():
        timestamps_dictionary[cam_id] = video_recorder.timestamps - shared_zero_time

    timestamp_diagnostics = calculate_camera_diagnostic_results(timestamps_dictionary)

    pprint(timestamp_diagnostics.dict())

    raw_frame_list_dictionary = {
        camera_id: video_recorder.frame_payload_list.copy()
        for camera_id, video_recorder in video_recorder_dictionary.items()
    }
    create_timestamp_diagnostic_plots(
        raw_frame_list_dictionary=raw_frame_list_dictionary,
        synchronized_frame_list_dictionary=synchronized_frame_list_dictionary,
        path_to_save_plots_png=Path(folder_to_save_plots)
        / "timestamp_diagnostic_plots.png",
        open_image_after_saving=show_plots_bool,
    )

    plot_first_and_last_frames(
        synchronized_frame_list_dictionary=synchronized_frame_list_dictionary,
        path_to_save_plots_png=Path(folder_to_save_plots) / "first_and_last_frames.png",
        open_image_after_saving=show_plots_bool,
    )
