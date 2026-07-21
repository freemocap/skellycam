import logging

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import AllTimestampsArray, AllDurationsArray, \
    FRAME_LIFECYCLE_TIMESTAMPS_DTYPE, CAMERA_TIMESTAMPS_CSV_ROW_DTYPE, FRAME_DURATION_DTYPE
from skellycam.utilities.time_unit_conversion import ns_to_sec, ns_to_ms

logger = logging.getLogger(__name__)


def create_and_save_camera_csvs(
        all_timestamps: AllTimestampsArray,
        all_durations: AllDurationsArray,
        recording_start_time_ns: int,
        recording_info: RecordingInfo,
        camera_configs: CameraConfigs,
        connection_frame_numbers: list[int],
        timebase_mapping: TimebaseMapping
) -> np.recarray:
    """
    Create and save per-camera CSV files with frame timestamps and durations.

    Args:
        all_timestamps: A 2D numpy recarray of shape (num_cameras, num_frames) containing frame lifecycle timestamps.
        all_durations: A 2D numpy recarray of shape (num_cameras, num_frames) containing frame duration metrics.
        recording_start_time_ns: The start time of the recording in nanoseconds.
        recording_info: An instance of RecordingInfo containing paths for saving CSV files.
        camera_configs: A list of camera configuration strings corresponding to each camera.
        connection_frame_numbers: A list of connection frame numbers corresponding to each frame.
        timebase_mapping: TimebaseMapping instance for converting timestamps.

    Returns:
        A numpy recarray containing all camera CSV rows.
    """
    num_cameras, num_frames = all_timestamps.shape
    connection_frame_numbers = np.array(connection_frame_numbers)

    all_camera_csv_rows = np.recarray((num_cameras, num_frames), dtype=CAMERA_TIMESTAMPS_CSV_ROW_DTYPE)

    # Process each camera's data in a vectorized way
    for camera_number, camera_id in enumerate(camera_configs.keys()):
        camera_frame_timestamps = all_timestamps[camera_number]
        camera_frame_durations = all_durations[camera_number]

        # Calculate main timestamps (midpoint between pre and post grab)
        frame_main_timestamps_ns = (
                                               camera_frame_timestamps.pre_frame_grab_ns + camera_frame_timestamps.post_frame_grab_ns) // 2

        # Fill in basic fields for all frames at once
        all_camera_csv_rows[camera_number]['recording_frame_number'] = np.arange(num_frames)
        all_camera_csv_rows[camera_number]['connection_frame_number'] = connection_frame_numbers
        all_camera_csv_rows[camera_number]['timestamp.from_recording_start.sec'] = ns_to_sec(
            frame_main_timestamps_ns - recording_start_time_ns)
        all_camera_csv_rows[camera_number]['timestamp.perf_counter_ns.ns'] = frame_main_timestamps_ns

        # Convert timestamps to UTC and local time
        utc_timestamps_ns = [timebase_mapping.convert_perf_counter_ns_to_unix_ns(
            timestamps_ns, local_time=False) for timestamps_ns in frame_main_timestamps_ns]
        all_camera_csv_rows[camera_number]['timestamp.utc.seconds'] = np.asarray(utc_timestamps_ns) / 1e9

        # Handle local ISO timestamps (still needs loop due to string formatting)
        for frame_number in range(num_frames):
            all_camera_csv_rows[camera_number, frame_number]['timestamp.local.iso8601'] = \
                timebase_mapping.convert_perf_counter_ns_to_local_iso8601(frame_main_timestamps_ns[frame_number])

        # Calculate frame durations and framerates (from previous frame)
        prev_frame_durations_ns = np.zeros(num_frames, dtype=np.float64)
        prev_frame_durations_ns[1:] = np.diff(frame_main_timestamps_ns)
        # Set first frame values to NaN
        prev_frame_durations_ns[0] = np.nan

        all_camera_csv_rows[camera_number]['from_previous.frame_duration.ms'] = prev_frame_durations_ns / 1e6

        # Calculate framerate (avoiding division by zero)
        framerates = np.zeros(num_frames, dtype=np.float64)
        valid_durations = prev_frame_durations_ns > 0
        framerates[valid_durations] = (prev_frame_durations_ns[valid_durations] / 1e9) ** -1  # Convert to Hz
        framerates[~valid_durations] = np.nan
        all_camera_csv_rows[camera_number]['from_previous.framerate.hz'] = framerates

        # Fill in all timestamp fields (vectorized)
        for field_name in FRAME_LIFECYCLE_TIMESTAMPS_DTYPE.names:
            csv_field = f'frame.{field_name.replace("_ns", "")}.ns'
            all_camera_csv_rows[camera_number][csv_field] = camera_frame_timestamps[
                                                                field_name] - recording_start_time_ns

        # Fill in all duration fields (vectorized)
        for field_name in FRAME_DURATION_DTYPE.names:
            if  "total" in field_name:
                csv_field = field_name.replace("_ns", ".ns").replace('total_', 'total.')
            else:
                csv_field = f'duration.{field_name.replace("_ns", ".ns")}'

            all_camera_csv_rows[camera_number][csv_field] = camera_frame_durations[
                field_name]

        # Save to CSV
        csv_file_path = recording_info.camera_timestamps_file_path_from_camera_id(camera_id)
        np.savetxt(csv_file_path, all_camera_csv_rows[camera_number], delimiter=',', fmt='%s',
                   header=",".join(CAMERA_TIMESTAMPS_CSV_ROW_DTYPE.names),
                   comments='')

    return all_camera_csv_rows


def create_camera_frame_csv_row_recarray(camera_frame_timestamps: np.recarray,
                                         camera_frame_durations: np.recarray,
                                         recording_frame_number: int,
                                         connection_frame_number: int,
                                         recording_start_time_ns: int,
                                         previous_frame_timestamp_ns: int | None = None,
                                         timebase_mapping: TimebaseMapping | None = None) -> tuple[
    TimebaseMapping, np.recarray]:
    if timebase_mapping is None:
        timebase_mapping = TimebaseMapping.from_numpy_record_array(camera_frame_timestamps.timebase_mapping)

    if not camera_frame_timestamps.dtype == FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
        raise ValueError(
            f"camera_frame_timestamps must be a numpy recarray with dtype FRAME_LIFECYCLE_TIMESTAMPS_DTYPE, got {type(camera_frame_timestamps)} with dtype {camera_frame_timestamps.dtype}")
    if not camera_frame_durations.dtype == FRAME_DURATION_DTYPE:
        raise ValueError(
            f"camera_frame_durations must be a numpy recarray with dtype FRAME_DURATION_DTYPE, got {type(camera_frame_durations)} with dtype {camera_frame_durations.dtype}")
    frame_main_timestamp_ns = (
                                      camera_frame_timestamps.pre_frame_grab_ns + camera_frame_timestamps.pre_frame_grab_ns) // 2  # Use midpoint of pre and post grab as main timestamp
    csv_row_recarray = np.recarray(1, dtype=CAMERA_TIMESTAMPS_CSV_ROW_DTYPE)
    csv_row_recarray['recording_frame_number'] = recording_frame_number
    csv_row_recarray['connection_frame_number'] = connection_frame_number
    csv_row_recarray['timestamp.from_recording_start.sec'] = ns_to_sec(
        frame_main_timestamp_ns - recording_start_time_ns)
    csv_row_recarray['timestamp.perf_counter_ns.ns'] = frame_main_timestamp_ns
    csv_row_recarray['timestamp.utc.seconds'] = ns_to_sec(
        timebase_mapping.convert_perf_counter_ns_to_unix_ns(frame_main_timestamp_ns, local_time=False))
    csv_row_recarray['timestamp.local.iso8601'] = timebase_mapping.convert_perf_counter_ns_to_local_iso8601(
        frame_main_timestamp_ns)
    if previous_frame_timestamp_ns is not None:
        prev_frame_duration_ns = frame_main_timestamp_ns - previous_frame_timestamp_ns
        csv_row_recarray['from_previous.frame_duration.ms'] = ns_to_ms(
            prev_frame_duration_ns) if prev_frame_duration_ns > 0 else np.nan
        csv_row_recarray['from_previous.framerate.hz'] = 1 / ns_to_sec(
            prev_frame_duration_ns) if prev_frame_duration_ns > 0 else np.nan
    else:
        csv_row_recarray['from_previous.frame_duration.ms'] = np.nan
        csv_row_recarray['from_previous.framerate.hz'] = np.nan

    # Fill in all timestamp fields
    csv_row_recarray['frame.initialized.ns'] = camera_frame_timestamps.initialized_ns - recording_start_time_ns
    csv_row_recarray['frame.pre_grab.ns'] = camera_frame_timestamps.pre_frame_grab_ns - recording_start_time_ns
    csv_row_recarray['frame.post_grab.ns'] = camera_frame_timestamps.post_frame_grab_ns - recording_start_time_ns
    csv_row_recarray['frame.pre_retrieve.ns'] = camera_frame_timestamps.pre_frame_retrieve_ns - recording_start_time_ns
    csv_row_recarray[
        'frame.post_retrieve.ns'] = camera_frame_timestamps.post_frame_retrieve_ns - recording_start_time_ns
    csv_row_recarray[
        'frame.pre_copy_to_camera_shm.ns'] = camera_frame_timestamps.pre_copy_to_camera_shm_ns - recording_start_time_ns
    csv_row_recarray[
        'frame.post_copy_to_camera_shm.ns'] = camera_frame_timestamps.post_copy_to_camera_shm_ns - recording_start_time_ns
    csv_row_recarray[
        'frame.pre_record_frame.ns'] = camera_frame_timestamps.pre_frame_record_ns - recording_start_time_ns
    csv_row_recarray[
        'frame.post_record_frame.ns'] = camera_frame_timestamps.post_frame_record_ns - recording_start_time_ns

    # Fill in all duration fields
    csv_row_recarray['duration.idle_before_frame_grab.ns'] = camera_frame_durations.idle_before_frame_grab_ns
    csv_row_recarray['duration.during_frame_grab.ns'] = camera_frame_durations.during_frame_grab_ns
    csv_row_recarray['duration.idle_before_retrieve.ns'] = camera_frame_durations.idle_before_retrieve_ns
    csv_row_recarray['duration.during_frame_retrieve.ns'] = camera_frame_durations.during_frame_retrieve_ns
    csv_row_recarray[
        'duration.idle_before_copy_to_camera_shm.ns'] = camera_frame_durations.idle_before_copy_to_camera_shm_ns
    csv_row_recarray['duration.during_copy_to_camera_shm.ns'] = camera_frame_durations.during_copy_to_camera_shm_ns
    csv_row_recarray['duration.idle_before_frame_record.ns'] = camera_frame_durations.idle_before_frame_record_ns
    csv_row_recarray['duration.during_frame_record.ns'] = camera_frame_durations.during_frame_record_ns
    csv_row_recarray['total.frame_processing_time.ns'] = camera_frame_durations.total_frame_processing_time_ns
    csv_row_recarray['total.camera_idle_time.ns'] = camera_frame_durations.total_camera_idle_time_ns

    return timebase_mapping, csv_row_recarray
