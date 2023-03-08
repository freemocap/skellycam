import logging
from pathlib import Path
from pprint import pprint
from typing import Dict, Union, List

import numpy as np

from skellycam.diagnostics.plot_first_middle_and_last_frames import plot_first_middle_and_last_frames
from skellycam.diagnostics.plot_framerate_diagnostics import (
    calculate_camera_diagnostic_results,
    create_timestamp_diagnostic_plots,
)
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.system.environment.default_paths import FIRST_MIDDLE_AND_LAST_FRAMES_FILE_NAME, \
    TIMESTAMP_DIAGNOSTIC_PLOTS_FILE_NAME

logger = logging.getLogger(__name__)


def create_diagnostic_plots(
        raw_timestamps: Dict[str, np.ndarray],
        synchronized_video_recorders: Dict[str, VideoRecorder],
        inter_camera_timestamp_differences: Dict[str, List[float]],
        folder_to_save_plots: Union[str, Path],
        shared_zero_time: Union[int, float] = 0,
        show_plots_bool: bool = True,
):
    logger.info("Creating diagnostic plots...")



    synchronized_timestamp_diagnostics = calculate_camera_diagnostic_results(synchronized_video_recorders)
    pprint(f"`Synchronized timestamp diagnostics`: \n {synchronized_timestamp_diagnostics.dict()}\n")

    create_timestamp_diagnostic_plots(
        raw_timestamps_dictionary=raw_timestamps,
        synchronized_timestamps_dictionary={camera_id: v.timestamps for camera_id, v in
                                            synchronized_video_recorders.items()},
        inter_camera_timestamp_differences=inter_camera_timestamp_differences,
        path_to_save_plots_png=Path(folder_to_save_plots) / TIMESTAMP_DIAGNOSTIC_PLOTS_FILE_NAME,
        open_image_after_saving=show_plots_bool,
    )

    plot_first_middle_and_last_frames(
        synchronized_frame_list_dictionary={camera_id: v.frame_list for camera_id, v in
                                   synchronized_video_recorders.items()},
        path_to_save_plots_png=Path(folder_to_save_plots) / FIRST_MIDDLE_AND_LAST_FRAMES_FILE_NAME,
        open_image_after_saving=show_plots_bool,
    )
