import numpy as np
import pandas as pd
from numpy import typing as npt

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import \
    calculate_frame_grab_timestamps, vectorized_ns_to_sec, calculate_framerate, vectorized_ns_to_ms
from skellycam.core.types.type_overloads import CameraIdString


def create_camera_dataframes(
        timestamps: npt.NDArray,
        durations: npt.NDArray,
        statistics: dict,
        recording_start_time_ns: int
) -> dict[CameraIdString, pd.DataFrame]:
    """
    Create DataFrames for individual camera timestamps suitable for CSV output.

    Args:
        timestamps: Array of timestamps with shape (num_cameras, num_frames)
        durations: Array of durations with shape (num_cameras, num_frames)
        statistics: Dictionary of statistics from process_recording_timestamps
        recording_start_time_ns: Recording start time in nanoseconds

    Returns:
        Dictionary mapping camera IDs to DataFrames
    """
    camera_ids = statistics['camera_ids']
    num_cameras = len(camera_ids)
    num_frames = timestamps.shape[1]

    camera_dfs = {}

    for i, camera_id in enumerate(camera_ids):
        # Calculate timestamp midpoints
        midpoints = calculate_frame_grab_timestamps(timestamps[i:i + 1])[0]

        # Calculate from recording start
        from_recording_start_sec = vectorized_ns_to_sec(midpoints - recording_start_time_ns)

        # Calculate framerates and durations
        framerates = calculate_framerate(midpoints)
        frame_durations_ms = vectorized_ns_to_ms(
            np.diff(midpoints, prepend=midpoints[0] - (midpoints[1] - midpoints[0])))

        # Create data dictionary
        data = {
            'recording_frame_number': np.arange(num_frames),
            'connection_frame_number': statistics['frame_numbers'],
            'timestamp.from_recording_start.sec': from_recording_start_sec,
            'timestamp.perf_counter_ns.ns': midpoints,
            'from_previous.frame_duration.ms': frame_durations_ms,
            'from_previous.framerate.hz': framerates,
        }

        # Add timestamp fields
        for field in timestamps.dtype.names:
            if field == 'timebase_mapping':
                # Skip timebase_mapping field as it is not numeric
                continue
            # Convert to nanoseconds relative to recording start
            field_ns = timestamps[i][field] - recording_start_time_ns

            # Add to data dictionary
            data[f'frame.{field.replace("_ns", "")}.ns'] = field_ns

        # Add duration fields
        for field in durations.dtype.names:
            # Add to data dictionary
            data[f'duration.{field.replace("_ns", "")}'] = durations[i][field]

        # Create DataFrame
        camera_dfs[camera_id] = pd.DataFrame(data)

    return camera_dfs
