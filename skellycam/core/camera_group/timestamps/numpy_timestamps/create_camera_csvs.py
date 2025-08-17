import logging
from datetime import timezone, datetime

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import \
    calculate_camera_timestamp_statistics
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import AllTimestampsArray, AllDurationsArray, \
    FRAME_LIFECYCLE_TIMESTAMPS_DTYPE, CAMERA_TIMESTAMPS_CSV_ROW_DTYPE, FRAME_DURATION_DTYPE, \
    MULI_FRAME_TIMESTAMP_CSV_ROW
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
        A dictionary mapping camera IDs to their respective CSV row recarrays.
    """
    num_cameras, num_frames = all_timestamps.shape

    all_camera_csv_rows = np.recarray((num_cameras, num_frames), dtype=CAMERA_TIMESTAMPS_CSV_ROW_DTYPE)

    for camera_number, camera_id in enumerate(camera_configs.keys()):
        camera_frame_timestamps = all_timestamps[camera_number]
        camera_frame_durations = all_durations[camera_number]

        previous_frame_timestamp_ns = None
        for frame_number in range(num_frames):
            (timebase_mapping, csv_row) = create_camera_frame_csv_row_recarray(
                camera_frame_timestamps=camera_frame_timestamps[frame_number],
                camera_frame_durations=camera_frame_durations[frame_number],
                recording_frame_number=frame_number,
                connection_frame_number=connection_frame_numbers[frame_number],
                recording_start_time_ns=recording_start_time_ns,
                previous_frame_timestamp_ns=previous_frame_timestamp_ns,
                timebase_mapping=timebase_mapping
            )
            all_camera_csv_rows[camera_number, frame_number] = csv_row
            previous_frame_timestamp_ns = csv_row['timestamp.perf_counter_ns.ns']  # Update for next frame

        # Save to CSV
        csv_file_path = recording_info.camera_timestamps_file_path_from_camera_id(camera_id)
        np.savetxt(csv_file_path, all_camera_csv_rows[camera_number], delimiter=',', fmt='%s',
                   header=",".join(CAMERA_TIMESTAMPS_CSV_ROW_DTYPE.names),
                   comments='')
        logger.debug(f"Saved camera {camera_id} timestamps CSV to {csv_file_path}")
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
    csv_row_recarray['frame.initialized.ns'] = camera_frame_timestamps.frame_initialized_ns - recording_start_time_ns
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
    csv_row_recarray['duration.total_frame_processing_time.ns'] = camera_frame_durations.total_frame_processing_time_ns

    return timebase_mapping, csv_row_recarray


def create_and_save_multiframe_csv(timestamps_rows_by_camera: np.recarray,
                                   recording_info: RecordingInfo) -> np.recarray:
    """
    Create a multiframe CSV that combines timestamps from all cameras.

    Args:
        timestamps_rows_by_camera: A dictionary mapping camera IDs to their respective CSV row recarrays.

    Returns:
        A numpy recarray containing the combined multiframe data.
    """
    if not timestamps_rows_by_camera.dtype == CAMERA_TIMESTAMPS_CSV_ROW_DTYPE:
        raise ValueError(f"timestamps_rows_by_camera must be a numpy recarray with dtype CAMERA_TIMESTAMPS_CSV_ROW, "
                         f"got {type(timestamps_rows_by_camera)} with dtype {timestamps_rows_by_camera.dtype}")

    (number_of_cameras, number_of_frames) = timestamps_rows_by_camera.shape
    multiframe_csv_rows = np.recarray(
        number_of_frames,
        dtype=MULI_FRAME_TIMESTAMP_CSV_ROW
    )

    skip_columns = ["connection_frame_number", 'timestamp.local.iso8601']
    mapped_column_names = {"recording_frame_number": "multiframe_number"}
    non_stats_column_names = ["timestamp.from_recording_start.sec",
                              "timestamp.perf_counter_ns.ns",
                              "timestamp.utc.seconds",
                              "timestamp.local.iso8601"]

    from_previous_column_names = ["from_previous.frame_duration.ms",
                                  "from_previous.framerate.hz"]

    # Combine timestamps from all cameras into the multiframe recarray
    for frame_number in range(number_of_frames):

        for column_name in CAMERA_TIMESTAMPS_CSV_ROW_DTYPE.names:
            if column_name in skip_columns:
                continue

            if column_name in mapped_column_names:
                value_set = set(timestamps_rows_by_camera[:, frame_number][column_name])
                if len(value_set) != 1:
                    raise ValueError(
                        f"Inconsistent values found for column '{column_name}' across cameras at frame {frame_number}. "
                        f"Expected all cameras to have the same value for this frame, received: {value_set}")
                multiframe_csv_rows[frame_number][mapped_column_names[column_name]] = value_set.pop()
                continue

            column_data_by_camera = timestamps_rows_by_camera[:, frame_number][column_name]
            assert column_data_by_camera.shape == (number_of_cameras,)
            if column_name in non_stats_column_names:
                multiframe_csv_rows[frame_number][column_name] = np.mean(column_data_by_camera)
                if column_name == "timestamp.utc.seconds":
                    # Create a datetime object from UTC seconds
                    utc_dt = datetime.fromtimestamp(multiframe_csv_rows[frame_number][column_name], tz=timezone.utc)

                    # Convert to local timezone
                    local_dt = utc_dt.astimezone()

                    multiframe_csv_rows[frame_number]["timestamp.local.iso8601"] = local_dt.isoformat()
                elif column_name == "timestamp.perf_counter_ns.ns":
                    multiframe_csv_rows[frame_number]["inter_camera_grab_range.ms"] = ns_to_ms(np.nanmax(column_data_by_camera) - np.nanmin(column_data_by_camera))

                continue

            if column_name in from_previous_column_names:
                if frame_number == 0:
                    multiframe_csv_rows[frame_number][column_name] = np.nan
                else:
                    multiframe_csv_rows[frame_number][column_name] = np.nanmean(
                        timestamps_rows_by_camera[:, frame_number][column_name])
                continue

            column_stats = calculate_camera_timestamp_statistics(
                data=(column_data_by_camera/1e6) if '.ns' in column_name else column_data_by_camera,
                axis="by_camera"
            )

            for stat_name in column_stats.dtype.names:
                stat_name.replace('_value', '')  # Remove '_value' suffix, which was added to avoid conflicts with builtin np st
                if  "min"  in stat_name or "max" in stat_name:
                    continue
                if "coefficient_of_variation" in stat_name:
                    mf_stat_column_name = column_name.replace('.ns', f'.proportion.{stat_name}')
                else:
                    mf_stat_column_name = column_name.replace('.ns', f'.ms.{stat_name}')

                multiframe_csv_rows[frame_number][mf_stat_column_name.replace('_value','')] = column_stats[stat_name]

    # Save to CSV
    np.savetxt(recording_info.timestamp_file_path,
               multiframe_csv_rows,
               delimiter=',',
               fmt='%s',
               header=",".join(MULI_FRAME_TIMESTAMP_CSV_ROW.names),
               comments='')
    logger.info(f"Saved multiframe timestamps CSV to {recording_info.timestamp_file_path}")
    return multiframe_csv_rows
