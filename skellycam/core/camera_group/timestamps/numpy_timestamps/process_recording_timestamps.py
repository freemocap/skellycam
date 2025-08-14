import numpy as np

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_frame_timestamp_statistics import \
    calculate_frame_timestamps_statistics
from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import calculate_durations
from skellycam.core.camera_group.timestamps.numpy_timestamps.timestamp_typed_dicts import StatsDict
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE, TimestampsArray, DurationArray, \
    FrameMetadataArray
from skellycam.core.types.type_overloads import CameraIdString


def process_recording_timestamps(
        frame_metadatas_by_camera: dict[CameraIdString, FrameMetadataArray],
        recording_start_time_ns: int,
        frame_numbers: list[int]
) -> tuple[TimestampsArray, DurationArray, StatsDict]:
    """
    Process all timestamps for a recording session.

    Args:
        timestamps_by_camera: Dictionary mapping camera IDs to timestamp arrays
        recording_start_time_ns: Recording start time in nanoseconds
        frame_numbers: Array of frame numbers for the recording session

    Returns:
        Tuple of (timestamps_array, durations_array, statistics_dict)
    """
    # Get dimensions
    camera_ids = list(frame_metadatas_by_camera.keys())
    num_cameras = len(camera_ids)
    num_frames = len(frame_numbers)

    # Create combined array for all cameras
    all_timestamps = np.recarray((num_cameras, num_frames), dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

    # Fill the array with data from each camera on each frame
    for frame_number in range(num_frames):
        for camera_index, camera_id in enumerate(camera_ids):
            all_timestamps[camera_index, frame_number] = frame_metadatas_by_camera[camera_id][frame_number].timestamps[0]

    # Calculate durations
    all_durations = calculate_durations(all_timestamps=all_timestamps)

    # Calculate statistics
    statistics = calculate_frame_timestamps_statistics(all_timestamps=all_timestamps,
                                                       all_durations=all_durations)

    # Add frame numbers and recording info to statistics
    statistics['frame_numbers'] = frame_numbers
    statistics['recording_start_time_ns'] = recording_start_time_ns
    statistics['camera_ids'] = camera_ids

    return all_timestamps, all_durations, statistics
