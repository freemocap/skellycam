import logging
from pathlib import Path
from typing import Dict, List, Union

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.diagnostics.create_diagnostic_plots import create_diagnostic_plots
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


def test_frame_synchronization(synchronized_frame_list_dictionary):
    frame_count_list = []

    for frame_list in synchronized_frame_list_dictionary.values():
        frame_count_list.append(len(frame_list))

    logger.info(f"frame_count_list: {frame_count_list}")

    assert np.all(
        np.diff(frame_count_list) == 0
    ), "Frame count is not the same for all cameras"

    logger.info("Test passed: Frame count is the same for all cameras :D")


def save_synchronized_videos(
    dictionary_of_video_recorders: Dict[str, VideoRecorder],
    folder_to_save_videos: Union[str, Path],
    create_diagnostic_plots_bool: bool = True,
    shared_zero_time: Union[int, float] = 0,
):
    logger.info(f"Saving synchronized videos to folder: {str(folder_to_save_videos)}")

    each_cam_raw_frame_list = []
    first_frame_timestamps = []
    final_frame_timestamps = []

    for video_recoder in dictionary_of_video_recorders.values():
        camera_frame_list = video_recoder._frame_payload_list
        first_frame_timestamps.append(camera_frame_list[0].timestamp_ns)
        final_frame_timestamps.append(camera_frame_list[-1].timestamp_ns)

        each_cam_raw_frame_list.append(camera_frame_list)

    latest_first_frame = np.max(first_frame_timestamps)
    earliest_final_frame = np.min(final_frame_timestamps)

    logger.info(f"first_frame_timestamps: {first_frame_timestamps}")
    logger.info(f"np.diff(first_frame_timestamps): {np.diff(first_frame_timestamps)}")
    logger.info(f"latest_first_frame: {latest_first_frame}")

    logger.info(f"final_frame_timestamps: {final_frame_timestamps}")
    logger.info(f"np.diff(final_frame_timestamps): {np.diff(final_frame_timestamps)}")
    logger.info(f"earliest_final_frame: {earliest_final_frame}")

    logger.info(f"----")
    logger.info(
        f"Clipping each camera's frame list to latest first frame and earliest final frame"
    )
    each_cam_clipped_frame_list = []
    each_cam_clipped_timestamp_list = []
    for og_frame_list in each_cam_raw_frame_list:
        each_cam_clipped_frame_list.append([])
        each_cam_clipped_timestamp_list.append([])
        for frame in og_frame_list:
            if frame.timestamp_ns < latest_first_frame:
                continue
            if frame.timestamp_ns > earliest_final_frame:
                continue

            each_cam_clipped_frame_list[-1].append(frame)
            each_cam_clipped_timestamp_list[-1].append(frame.timestamp_ns)

    number_of_frames_per_camera_clipped = [len(f) for f in each_cam_clipped_frame_list]
    min_number_of_frames = np.min(number_of_frames_per_camera_clipped)
    index_of_the_camera_with_fewest_frames = np.argmin(
        number_of_frames_per_camera_clipped
    )

    reference_frame_list = each_cam_clipped_frame_list[
        index_of_the_camera_with_fewest_frames
    ]

    logger.info(
        "Creating synchronized frame list by matching each camera's timestamps to the timestamps of the camera with the fewest frames"
    )
    logger.info(
        "TODO - Make a reference timestamp list based on the desired/measured framerate (while ensuring we won't throw away good frames...)"
    )
    logger.info("NOTE - this is a slow process, I think it's like O(n^2) or something")
    synchronized_frame_list_dictionary = {}
    for camera_id, camera_frame_list in enumerate(each_cam_clipped_frame_list):
        logger.info(f"Creating synchronized frame list for camera {camera_id}...")
        cam_synchronized_frame_list = []
        for reference_frame in reference_frame_list:
            closest_frame = get_nearest_frame(camera_frame_list, reference_frame)
            cam_synchronized_frame_list.append(closest_frame)
        synchronized_frame_list_dictionary[str(camera_id)] = cam_synchronized_frame_list

    logger.info(
        f" (clipped) number_of_frames_per_camera: {number_of_frames_per_camera_clipped}, min:{min_number_of_frames}"
    )

    final_frame_timestamps = [
        frame_list[-1].timestamp_ns
        for frame_list in synchronized_frame_list_dictionary.values()
    ]

    logger.info(f"np.diff(final_frame_timestamps): {np.diff(final_frame_timestamps)}")

    test_frame_synchronization(synchronized_frame_list_dictionary)

    Path(folder_to_save_videos).mkdir(parents=True, exist_ok=True)
    for camera_id, frame_list in synchronized_frame_list_dictionary.items():
        logger.info(
            f" Saving camera {camera_id} video with {len(frame_list)} frames..."
        )
        dictionary_of_video_recorders[camera_id].save_frame_list_to_video_file(
            list_of_frames=frame_list,
            path_to_save_video_file=Path(folder_to_save_videos)
            / f"Camera_{str(camera_id).zfill(3)}_synchronized.mp4",
        )
    if create_diagnostic_plots_bool:
        create_diagnostic_plots(
            video_recorder_dictionary=dictionary_of_video_recorders,
            synchronized_frame_list_dictionary=synchronized_frame_list_dictionary,
            folder_to_save_plots=folder_to_save_videos,
            shared_zero_time=shared_zero_time,
            show_plots_bool=True,
        )
    return synchronized_frame_list_dictionary


def get_nearest_frame(frame_list, reference_frame) -> FramePayload:
    timestamps = gather_timestamps(frame_list)

    close_frame_index = np.argmin(np.abs(timestamps - reference_frame.timestamp_ns))

    return frame_list[close_frame_index]


def gather_timestamps(frame_list: List[FramePayload]) -> np.ndarray:
    timestamps_npy = np.empty(0)
    for frame in frame_list:
        timestamps_npy = np.append(timestamps_npy, frame.timestamp_ns)

    return timestamps_npy
