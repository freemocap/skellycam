from skellycam.core.types.timestamp_types import TimestampStats

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import \
    calculate_frame_grab_timestamps, calculate_statistics
from skellycam.core.types.numpy_record_dtypes import AllTimestampsArray, AllDurationsArray


def calculate_frame_timestamps_statistics(all_timestamps: AllTimestampsArray,
                                          all_durations: AllDurationsArray) -> TimestampStats:
    """
    Calculate statistics for all timestamp and duration fields across cameras.

    Args:
        all_timestamps: Array of timestamps with shape (num_cameras, num_frames)
        all_durations: Array of durations with shape (num_cameras, num_frames)

    Returns:
        Dictionary of statistics arrays for each field
    """
    if not (all_timestamps.shape == all_durations.shape):
        raise ValueError("Timestamps and durations arrays must have the same shape.")
    # Calculate midpoints first
    all_frame_grab_timestamps = calculate_frame_grab_timestamps(all_timestamps)


    # Calculate statistics for midpoints (across cameras)
    frame_grab_stats = calculate_statistics(all_frame_grab_timestamps, axis=0)

    # Calculate statistics for all timestamp fields
    timestamp_stats_dict = {}
    for field in all_timestamps.dtype.names:
        if field == 'timebase_mapping':
            # Skip timebase_mapping field as it is not numeric
            continue
        timestamp_stats_dict[field] = calculate_statistics(all_timestamps[field], axis=0)
    timestamp_stats = TimestampStats(**timestamp_stats_dict)
    # Calculate statistics for all duration fields
    duration_stats = {}
    for field in all_durations.dtype.names:
        duration_stats[field] = calculate_statistics(all_durations[field], axis=0)

    # Combine all statistics
    stats = {
        'frame_grab_timestamps': frame_grab_stats,
        'timestamps': timestamp_stats,
        'durations': duration_stats
    }

    return stats
