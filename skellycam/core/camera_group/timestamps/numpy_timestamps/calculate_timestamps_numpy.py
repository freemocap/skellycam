import logging
from typing import Literal

import numpy as np
import numpy.typing as npt

from skellycam.core.types.numpy_record_dtypes import FRAME_DURATION_DTYPE,  DurationArray, StatsArray, \
    FloatArray, IntArray, AllTimestampsArray, AllFrameGrabTimestampsArray
from skellycam.core.types.numpy_record_dtypes import STATS_DTYPE

logger = logging.getLogger(__name__)



def calculate_frame_grab_timestamps(all_timestamps: AllTimestampsArray) -> AllFrameGrabTimestampsArray:
    """
    Calculate the midpoint between pre_frame_grab_ns and post_frame_grab_ns for all frames.

    Args:
        all_timestamps: Array of timestamps with shape (num_cameras, num_frames)

    Returns:
        Array of midpoint timestamps with shape (num_cameras, num_frames)
    """
    (num_cams, num_frames) = all_timestamps.shape
    frame_grab_timestamps = np.zeros(all_timestamps.shape, dtype=np.int64)

    for camera_number in range(num_cams):
        for frame_number in range(num_frames):
            frame_grab_timestamps[camera_number, frame_number] = (all_timestamps[camera_number, frame_number].pre_frame_grab_ns + all_timestamps[camera_number, frame_number].post_frame_grab_ns) // 2

    return frame_grab_timestamps


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
            durations.idle_before_frame_grab_ns = timestamps.post_frame_grab_ns - timestamps.pre_frame_grab_ns
            durations.during_frame_grab_ns = timestamps.post_frame_grab_ns - timestamps.pre_frame_grab_ns
            durations.idle_before_retrieve_ns = timestamps.pre_frame_retrieve_ns - timestamps.post_frame_grab_ns
            durations.during_frame_retrieve_ns = timestamps.post_frame_retrieve_ns - timestamps.pre_frame_retrieve_ns
            durations.idle_before_copy_to_camera_shm_ns = timestamps.pre_copy_to_camera_shm_ns - timestamps.post_frame_retrieve_ns
            durations.during_copy_to_camera_shm_ns = timestamps.post_copy_to_camera_shm_ns - timestamps.pre_copy_to_camera_shm_ns
            durations.idle_before_frame_record_ns = timestamps.pre_frame_record_ns - timestamps.post_copy_to_camera_shm_ns
            durations.during_frame_record_ns = timestamps.post_frame_record_ns - timestamps.pre_frame_record_ns
            durations.total_frame_processing_time_ns = timestamps.post_frame_record_ns - timestamps.pre_frame_grab_ns

             # Store the calculated durations
            all_durations[camera_number, frame_number] = durations

    return all_durations


def calculate_camera_timestamp_statistics(data: npt.NDArray, axis: Literal["by_camera", "by_frame"]) -> np.recarray:
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
        raise ValueError("Input data array is empty.")


    # Create output array with the appropriate shape
    axis_num = 0 if axis == "by_camera" else 1
    if axis_num > data.ndim - 1:
        raise ValueError(f"Invalid axis '{axis}' for data with shape {data.shape}. Axis must be 'by_camera' or 'by_frame'.")
    output_shape = list(data.shape)
    output_shape.pop(axis_num)
    stats = np.recarray(tuple(output_shape), dtype=STATS_DTYPE)

    # Calculate statistics
    stats.mean_value = np.nanmean(data, axis=axis_num)
    stats.median_value = np.nanmedian(data, axis=axis_num)
    stats.standard_deviation_value = np.nanstd(data, axis=axis_num)
    stats.coefficient_of_variation_value = np.abs(np.nanstd(data, axis=axis_num) / np.nanmean(data, axis=axis_num)) if np.nanmean(data, axis=axis_num) != 0 else np.nan
    stats.min_value = np.nanmin(data, axis=axis_num)
    stats.max_value = np.nanmax(data, axis=axis_num)
    stats.range_value = np.nanmax(data, axis=axis_num) -  np.nanmin(data, axis=axis_num)

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


