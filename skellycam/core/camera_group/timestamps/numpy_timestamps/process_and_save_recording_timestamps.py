from typing import Optional

import numpy as np

from skellycam.core.camera_group.timestamps.numpy_timestamps.process_recording_timestamps import \
    process_recording_timestamps
from skellycam.core.camera_group.timestamps.numpy_timestamps.create_multiframe_timestamps_dataframe import \
    create_multiframe_dataframe
from skellycam.core.camera_group.timestamps.numpy_timestamps.create_camera_dataframes import create_camera_dataframes
from skellycam.core.camera_group.timestamps.numpy_timestamps.save_timestamps_statistics_summary import \
    save_timestamp_statistics_summary
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import FrameMetadataArray
from skellycam.core.types.type_overloads import CameraIdString

import  logging
logger = logging.getLogger(__name__)

def validate_frame_metadatas(frame_metadatas_by_camera: dict[CameraIdString, FrameMetadataArray]) -> list[int]:
    """
    Validate that all frame metadatas contain the same number of frames, and that the frame numbers match within each cameras' metadata.

    Args:
        frame_metadatas_by_camera: Dictionary mapping camera IDs to arrays of frame metadata.

    Raises:
        ValueError: If the number of frames is inconsistent across cameras.
    """
    num_frames = None
    for camera_id, frame_metadatas in frame_metadatas_by_camera.items():
        if num_frames is None:
            num_frames = len(frame_metadatas)
        elif len(frame_metadatas) != num_frames:
            raise ValueError(f"Camera {camera_id} has {len(frame_metadatas)} frames, expected {num_frames} frames.")

    # Check that frame numbers are consistent across cameras
    frame_numbers = []
    for frame_number in range(num_frames):
        frame_number = set([metadata[frame_number].frame_number[0] for metadata in frame_metadatas_by_camera.values()])
        if len(frame_number) != 1:
            raise ValueError(f"Inconsistent frame numbers found across cameras: {frame_number}. "
                             f"Expected all cameras to have the same frame numbers.")
        frame_numbers.append(frame_number.pop())

    return frame_numbers

def process_and_save_recording_timestamps(
        frame_metadatas_by_camera: dict[CameraIdString, FrameMetadataArray],
        recording_info: RecordingInfo,
) -> None:
    frame_numbers = validate_frame_metadatas(frame_metadatas_by_camera)

    # Find the earliest timestamp as recording start time
    first_timestamps = {camera_id: md[0].timestamps[0] for camera_id, md in frame_metadatas_by_camera.items()}
    recording_start_time_ns = min(
        np.min(ts.pre_frame_grab_ns) for ts in first_timestamps.values()
    )

    # Process timestamps
    timestamps, durations, statistics = process_recording_timestamps(
        frame_metadatas_by_camera=frame_metadatas_by_camera,
        recording_start_time_ns=recording_start_time_ns,
        frame_numbers=frame_numbers,
    )

    # Create multiframe DataFrame
    multiframe_df = create_multiframe_dataframe(statistics, recording_start_time_ns)

    # Create camera DataFrames
    camera_dfs = create_camera_dataframes(timestamps, durations, statistics, recording_start_time_ns)

    # Save multiframe DataFrame
    multiframe_df.to_csv(recording_info.timestamp_file_path, index=False)
    logger.info(f"Saved multiframe timestamps to {recording_info.timestamp_file_path}")

    # Save camera DataFrames
    for camera_id, df in camera_dfs.items():
        output_path = recording_info.camera_timestamps_file_path_from_camera_id(camera_id)
        df.to_csv(output_path, index=False)
        logger.debug(f"Saved camera {camera_id} timestamps to {output_path}")

    # Save statistics summary
    save_timestamp_statistics_summary(statistics, recording_info, frame_metadatas_by_camera)

    logger.info(f"Successfully processed and saved timestamps for recording {recording_info.recording_name}")
