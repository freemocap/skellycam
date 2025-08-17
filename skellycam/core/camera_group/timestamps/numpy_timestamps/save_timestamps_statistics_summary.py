import numpy as np

from skellycam.core.camera_group.timestamps.numpy_timestamps.calculate_timestamps_numpy import calculate_framerate, vectorized_ns_to_ms, vectorized_ns_to_sec, logger
from skellycam.core.types.timestamp_types import TimestampStats
from skellycam.core.types.numpy_record_dtypes import TimestampsArray
from skellycam.core.camera_group.timestamps.numpy_timestamps.generate_timestamps_stats_text_report import \
    generate_timestamps_stats_text_report
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString


def save_timestamp_statistics_summary(
        ts_statistics: TimestampStats,
        recording_info: RecordingInfo,
        timestamps_by_camera: dict[CameraIdString, TimestampsArray]
) -> None:
    """
    Generate and save a summary of timestamp statistics.

    Args:
        ts_statistics: Dictionary of statistics from process_recording_timestamps
        recording_info: RecordingInfo object with paths for saving
        timestamps_by_camera: Dictionary mapping camera IDs to timestamp arrays
    """
    # Calculate overall statistics
    num_cameras = len(timestamps_by_camera)
    num_frames = len(next(iter(timestamps_by_camera.values())))

    # Calculate framerate statistics
    timestamps_ns = ts_statistics['frame_grab_timestamps']['mean']
    framerates = calculate_framerate(timestamps_ns)[1:]  # Skip first NaN
    framerate_stats = {
        'mean': np.nanmean(framerates),
        'median': np.nanmedian(framerates),
        'std': np.nanstd(framerates),
        'min': np.nanmin(framerates),
        'max': np.nanmax(framerates),
    }

    # Calculate frame duration statistics
    frame_durations_ms = vectorized_ns_to_ms(np.diff(timestamps_ns))
    frame_duration_stats = {
        'mean': np.nanmean(frame_durations_ms),
        'median': np.nanmedian(frame_durations_ms),
        'std': np.nanstd(frame_durations_ms),
        'min': np.nanmin(frame_durations_ms),
        'max': np.nanmax(frame_durations_ms),
    }

    # Calculate inter-camera grab range statistics
    inter_camera_grab_range_ms = vectorized_ns_to_ms(ts_statistics['frame_grab_timestamps']['range'])
    inter_camera_stats = {
        'mean': np.nanmean(inter_camera_grab_range_ms),
        'median': np.nanmedian(inter_camera_grab_range_ms),
        'std': np.nanstd(inter_camera_grab_range_ms),
        'min': np.nanmin(inter_camera_grab_range_ms),
        'max': np.nanmax(inter_camera_grab_range_ms),
    }

    # Calculate total duration
    total_duration_sec = vectorized_ns_to_sec(timestamps_ns[-1] - timestamps_ns[0])

    # Create summary dictionary
    summary = {
        'recording_name': recording_info.recording_name,
        'number_of_cameras': num_cameras,
        'number_of_frames': num_frames,
        'total_duration_sec': float(total_duration_sec),
        'framerate_stats': framerate_stats,
        'frame_duration_stats': frame_duration_stats,
        'inter_camera_grab_range_ms': inter_camera_stats,
    }

    # Add duration statistics
    for field in ts_statistics['durations']:
        field_name = field.replace('_ns', '_ms')
        summary[field_name] = {
            'mean': float(np.nanmean(vectorized_ns_to_ms(ts_statistics['durations'][field]['mean']))),
            'median': float(np.nanmedian(vectorized_ns_to_ms(ts_statistics['durations'][field]['median']))),
            'std': float(np.nanmean(vectorized_ns_to_ms(ts_statistics['durations'][field]['std']))),
            'min': float(np.nanmin(vectorized_ns_to_ms(ts_statistics['durations'][field]['min']))),
            'max': float(np.nanmax(vectorized_ns_to_ms(ts_statistics['durations'][field]['max']))),
        }

    # Save as JSON
    import json
    with open(recording_info.timestamp_stats_json_file_path, 'w') as f:
        json.dump(summary, f, indent=2)

    # Generate and save text report
    text_report = generate_timestamps_stats_text_report(summary)
    with open(recording_info.timestamp_stats_text_file_path, 'w', encoding='utf-8') as f:
        f.write(text_report)

    logger.info(f"Saved timestamp statistics to {recording_info.timestamp_stats_json_file_path}")
