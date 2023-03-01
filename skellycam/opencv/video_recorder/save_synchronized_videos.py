import logging
from copy import deepcopy
from pathlib import Path
from typing import Dict, Union

import numpy as np
from tqdm import tqdm

from skellycam.diagnostics.create_diagnostic_plots import create_diagnostic_plots
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.tests.test_frame_timestamp_synchronization import test_frame_timestamp_synchronization
from skellycam.tests.test_synchronized_video_frame_counts import test_synchronized_video_frame_counts
from skellycam.utilities.is_monotonic import is_monotonic

logger = logging.getLogger(__name__)


def save_synchronized_videos(
        raw_video_recorders: Dict[str, VideoRecorder],
        folder_to_save_videos: Union[str, Path],
        create_diagnostic_plots_bool: bool = True,
):
    logger.info(f"Saving synchronized videos to folder: {str(folder_to_save_videos)}")

    raw_timestamps_by_cameras = {camera_id: video_recorder.timestamps for camera_id, video_recorder in raw_video_recorders.items()}
    first_frame_timestamps = np.asarray(
        [video_recorder.frame_list[0].timestamp_ns for video_recorder in raw_video_recorders.values()])
    final_frame_timestamps = np.asarray(
        [video_recorder.frame_list[-1].timestamp_ns for video_recorder in raw_video_recorders.values()])

    latest_first_frame = np.max(first_frame_timestamps)
    earliest_final_frame = np.min(final_frame_timestamps)

    assert latest_first_frame < earliest_final_frame, "The `latest_first_frame` is not before the `earliest_final_frame`!"

    logger.info(f"first_frame_timestamps: {str(first_frame_timestamps / 1e9)} seconds")
    logger.info(f"np.diff(first_frame_timestamps): {str(np.diff(first_frame_timestamps) / 1e9)} seconds")
    logger.info(f"latest_first_frame: {str(latest_first_frame / 1e9)} seconds")

    logger.info(f"final_frame_timestamps: {str(final_frame_timestamps / 1e9)} seconds")
    logger.info(f"np.diff(final_frame_timestamps): {str(np.diff(final_frame_timestamps) / 1e9)} seconds")
    logger.info(f"earliest_final_frame: {str(earliest_final_frame / 1e9)} seconds")

    logger.info(f"Recording duration: {str((earliest_final_frame - latest_first_frame) / 1e9)} seconds")

    frame_duration_ns_per_camera = np.asarray([video_recorders.median_frame_duration_ns for video_recorders in
                                               raw_video_recorders.values()])
    mean_frame_duration_ns = np.mean(frame_duration_ns_per_camera)
    logger.info(
        f"frame_duration_ns_per_camera: {frame_duration_ns_per_camera / 1e9}, mean:{mean_frame_duration_ns / 1e9} seconds per frame")

    reference_timestamps = np.arange(latest_first_frame, earliest_final_frame, mean_frame_duration_ns)

    logger.info(
        f"reference number of frames: {len(reference_timestamps)},"
        f" raw video number of frames: {[v.number_of_frames for v in raw_video_recorders.values()]}")

    synchronized_video_recorders = {}
    for camera_id, video_recorder in raw_video_recorders.items():
        logger.info(f"Creating synchronized frame list for camera {camera_id}...")

        assert is_monotonic(video_recorder.timestamps), "Video timestamps are not monotonic!"

        synchronized_video_path = Path(folder_to_save_videos) / f"Camera_{str(camera_id).zfill(3)}_synchronized.mp4"
        synchronized_video_recorders[camera_id] = VideoRecorder(video_file_save_path=synchronized_video_path)

        raw_frame_list = video_recorder.frame_list
        for reference_frame_number, reference_frame_timestamp in enumerate(reference_timestamps):
            previous_frame = deepcopy(raw_frame_list[0])
            for frame_number, frame in enumerate(raw_frame_list):
                frame_timestamp_difference = reference_frame_timestamp - frame.timestamp_ns
                if abs(frame_timestamp_difference) < mean_frame_duration_ns:
                    raw_frame_list.pop(frame_number)
                    previous_frame = deepcopy(frame)
                    synchronized_video_recorders[camera_id].append_frame_payload_to_list(frame)
                    break
                elif frame_timestamp_difference > mean_frame_duration_ns * 3 or frame_number == len(raw_frame_list) - 1:
                    synchronized_video_recorders[camera_id].append_frame_payload_to_list(previous_frame)
                    break


    test_frame_timestamp_synchronization(synchronized_frame_list_dictionary={camera_id: v.frame_list for camera_id, v in
                                          synchronized_video_recorders.items()})

    Path(folder_to_save_videos).mkdir(parents=True, exist_ok=True)
    for camera_id, synchronized_video_recorder in synchronized_video_recorders.items():
        logger.info(
            f" Saving camera {camera_id} video with {synchronized_video_recorder.number_of_frames} frames..."
        )
        synchronized_video_recorder.save_frame_list_to_video_file()

    if create_diagnostic_plots_bool:
        create_diagnostic_plots(
            raw_timestamps_by_camera=raw_timestamps_by_cameras,
            synchronized_video_recorders=synchronized_video_recorders,
            folder_to_save_plots=folder_to_save_videos,
            show_plots_bool=True,
        )

    test_synchronized_video_frame_counts(video_folder_path=folder_to_save_videos)

    logger.info(f"Done!")
