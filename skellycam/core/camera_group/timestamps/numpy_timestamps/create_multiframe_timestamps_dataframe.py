import numpy as np
import pandas as pd

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import vectorized_ns_to_sec, calculate_framerate, vectorized_ns_to_ms

def create_multiframe_dataframe(
        ts_statistics: TimestampStats,
        recording_start_time_ns: int
) -> pd.DataFrame:
    """
    Create a DataFrame for multiframe timestamps suitable for CSV output.

    Args:
        ts_statistics: Dictionary of statistics from process_recording_timestamps
        recording_start_time_ns: Recording start time in nanoseconds

    Returns:
        DataFrame with multiframe timestamp data
    """
    num_frames = len(ts_statistics['frame_numbers'])

    # Calculate timestamp frame_grab_timestamps_ns relative to recording start
    frame_grab_timestamps_ns = ts_statistics['frame_grab_timestamps']['mean']
    from_recording_start_sec = vectorized_ns_to_sec(frame_grab_timestamps_ns - recording_start_time_ns)

    # Calculate framerates
    framerates = calculate_framerate(frame_grab_timestamps_ns)
    frame_durations_ms = vectorized_ns_to_ms(np.diff(frame_grab_timestamps_ns, prepend=frame_grab_timestamps_ns[0] - (frame_grab_timestamps_ns[1] - frame_grab_timestamps_ns[0])))

    # Calculate inter-camera grab range
    inter_camera_grab_range_ms = vectorized_ns_to_ms(ts_statistics['frame_grab_timestamps']['range'])

    # Create DataFrame
    data = {
        'recording_frame_number': np.arange(num_frames),
        'connection_frame_number': ts_statistics['frame_numbers'],
        'timestamp.from_recording_start.sec': from_recording_start_sec,
        'timestamp.perf_counter_ns.ns': frame_grab_timestamps_ns,
        'from_previous.frame_duration.ms': frame_durations_ms,
        'from_previous.framerate.hz': framerates,
        'multiframe.inter_camera_grab_range.ms': inter_camera_grab_range_ms,
    }

    # Add duration statistics (mean and std)
    for field in ts_statistics['durations']:
        # Convert to milliseconds
        mean_ms = vectorized_ns_to_ms(ts_statistics['durations'][field]['mean'])
        std_ms = vectorized_ns_to_ms(ts_statistics['durations'][field]['std'])

        # Add to data dictionary
        data[f'duration.{field.replace("_ns", "")}.mean.ms'] = mean_ms
        data[f'duration.{field.replace("_ns", "")}.std.ms'] = std_ms

    # Add timestamp statistics (mean and std)
    for field in ts_statistics['timestamps']:
        # Convert to milliseconds relative to recording start
        field_ms = vectorized_ns_to_ms(ts_statistics['timestamps'][field]['mean'] - recording_start_time_ns)
        field_std_ms = vectorized_ns_to_ms(ts_statistics['timestamps'][field]['std'])

        # Add to data dictionary
        data[f'frame.{field.replace("_ns", "")}.mean.ms'] = field_ms
        data[f'frame.{field.replace("_ns", "")}.std.ms'] = field_std_ms

    return pd.DataFrame(data)
