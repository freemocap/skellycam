from datetime import datetime, timezone

import numpy as np

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import calculate_statistics

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import CAMERA_TIMESTAMPS_CSV_ROW_DTYPE, MULTI_FRAME_TIMESTAMP_CSV_ROW
from skellycam.utilities.time_unit_conversion import ns_to_ms

import logging
logger = logging.getLogger(__name__)

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
        dtype=MULTI_FRAME_TIMESTAMP_CSV_ROW
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
                    multiframe_csv_rows[frame_number]["inter_camera.frame_grab_range.ms"] = ns_to_ms(np.nanmax(column_data_by_camera) - np.nanmin(column_data_by_camera))

                continue

            if column_name in from_previous_column_names:
                if frame_number == 0:
                    multiframe_csv_rows[frame_number][column_name] = np.nan
                else:
                    multiframe_csv_rows[frame_number][column_name] = np.nanmean(
                        timestamps_rows_by_camera[:, frame_number][column_name])
                continue

            column_stats = calculate_statistics(
                data=(column_data_by_camera/1e6) if '.ns' in column_name else column_data_by_camera,
                axis=0
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
               header=",".join(MULTI_FRAME_TIMESTAMP_CSV_ROW.names),
               comments='')
    # logger.info(f"Saved multiframe timestamps CSV to {recording_info.timestamp_file_path}")
    return multiframe_csv_rows
