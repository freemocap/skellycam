import logging
from typing import Literal

import numpy as np
import numpy.typing as npt

from skellycam.core.types.numpy_record_dtypes import FRAME_DURATION_DTYPE,  DurationArray, StatsArray, \
    FloatArray, IntArray, AllTimestampsArray, AllFrameGrabTimestampsArray
from skellycam.core.types.numpy_record_dtypes import STATS_DTYPE

logger = logging.getLogger(__name__)



def calculate_frame_grab_timestamps(timestamps: AllTimestampsArray) -> AllFrameGrabTimestampsArray:
    """
    Calculate the midpoint between pre_frame_grab_ns and post_frame_grab_ns for all frames.

    Args:
        timestamps: Array of timestamps with shape (num_cameras, num_frames)

    Returns:
        Array of midpoint timestamps with shape (num_cameras, num_frames)
    """
    (num_cams, num_frames) = timestamps.shape
    frame_grabs = np.zeros(timestamps.shape, dtype=np.int64)

    for camera_number in range(num_cams):
        for frame_number in range(num_frames):
            frame_grabs[num_cams, num_frames] = (timestamps.pre_frame_grab_ns + timestamps.post_frame_grab_ns) // 2

    return frame_grabs


def calculate_durations(all_timestamps: AllTimestampsArray) -> DurationArray:
    """
    Calculate all duration metrics from raw timestamps.

    Args:
        all_timestamps: Array of timestamps with shape (num_cameras, num_frames)

    Returns:
        Array of durations with shape (num_cameras, num_frames)
    """
    # Create output array
    num_cameras, num_frames = all_timestamps.shape
    all_durations = np.recarray((num_cameras,num_frames), dtype=FRAME_DURATION_DTYPE)

    for camera_number in range(num_cameras):
        for frame_number in range(num_frames):
            # Extract timestamps for the current camera and frame
            timestamps = all_timestamps[camera_number, frame_number]
            durations = np.recarray(1, dtype=FRAME_DURATION_DTYPE)

            # Calculate all durations in a vectorized way
            durations.during_frame_grab_ns = timestamps.post_frame_grab_ns - timestamps.pre_frame_grab_ns
            durations.idle_before_retrieve_ns = timestamps.pre_frame_retrieve_ns - timestamps.post_frame_grab_ns
            durations.during_frame_retrieve_ns = timestamps.post_frame_retrieve_ns - timestamps.pre_frame_retrieve_ns
            durations.idle_before_copy_to_camera_shm_ns = timestamps.pre_copy_to_camera_shm_ns - timestamps.post_frame_retrieve_ns
            durations.during_copy_to_camera_shm_ns = timestamps.post_copy_to_camera_shm_ns - timestamps.pre_copy_to_camera_shm_ns
            durations.idle_before_frame_record_ns = timestamps.pre_frame_record_ns - timestamps.post_copy_to_camera_shm_ns
            durations.during_frame_record_ns = timestamps.post_frame_record_ns - timestamps.pre_frame_record_ns
            durations.total_frame_processing_time_ns = timestamps.post_frame_record_ns - timestamps.pre_frame_grab_ns
            durations.total_camera_idle_time_ns = timestamps.pre_frame_grab_ns - timestamps.frame_initialized_ns

             # Store the calculated durations
            all_durations[camera_number, frame_number] = durations

    return all_durations


def calculate_statistics(data: npt.NDArray, axis: Literal[0, 1]) -> StatsArray:
    """
    Calculate descriptive statistics for the given data along the specified axis.

    Args:
        data: Input data array
        axis: Axis along which to calculate statistics (0 for across cameras, 1 for across frames)

    Returns:
        Array of statistics
    """
    # Handle empty or single-value arrays
    if data.size == 0:
        return np.zeros(1, dtype=STATS_DTYPE)

    # Create output array with the appropriate shape
    output_shape = list(data.shape)
    output_shape.pop(axis)
    stats = np.zeros(tuple(output_shape), dtype=STATS_DTYPE)

    # Calculate statistics
    with np.errstate(invalid='ignore'):  # Ignore NaN warnings
        stats.mean = np.nanmean(data, axis=axis)
        stats.median = np.nanmedian(data, axis=axis)
        stats.std = np.nanstd(data, axis=axis)
        stats.min = np.nanmin(data, axis=axis)
        stats.max = np.nanmax(data, axis=axis)
        stats.range = stats.max - stats.min

    return stats


def vectorized_ns_to_ms(ns_array: npt.NDArray[np.number]) -> FloatArray:
    """Convert nanoseconds to milliseconds in a vectorized way."""
    return ns_array / 1e6


def vectorized_ns_to_sec(ns_array: npt.NDArray[np.number]) -> FloatArray:
    """Convert nanoseconds to seconds in a vectorized way."""
    return ns_array / 1e9


def vectorized_ms_to_sec(ms_array: npt.NDArray) -> npt.NDArray:
    """Convert milliseconds to seconds in a vectorized way."""
    return ms_array / 1e3


def calculate_framerate(timestamp_midpoints: IntArray) -> FloatArray:
    """
    Calculate framerate from timestamp midpoints.

    Args:
        timestamp_midpoints: Array of timestamp midpoints in nanoseconds

    Returns:
        Array of framerates in Hz
    """
    # Calculate time differences between consecutive frames
    time_diffs_ns = np.diff(timestamp_midpoints)

    # Convert to seconds and calculate framerate
    time_diffs_sec = vectorized_ns_to_sec(time_diffs_ns)

    # Handle zero or negative time differences
    valid_diffs = time_diffs_sec > 0
    framerates = np.zeros_like(time_diffs_sec)
    framerates[valid_diffs] = 1.0 / time_diffs_sec[valid_diffs]

    # Pad with NaN for the first frame
    return np.concatenate(([np.nan], framerates))


