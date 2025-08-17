import logging
import time

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.timestamps.numpy_timestamps.create_camera_csvs import create_and_save_camera_csvs, \
    create_and_save_multiframe_csv
from skellycam.core.camera_group.timestamps.numpy_timestamps.process_recording_timestamps import \
    process_recording_timestamps
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


def validate_frame_metadatas(frame_metadatas_by_camera: dict[CameraIdString, list[np.recarray]],
                             camera_configs: CameraConfigs) -> tuple[list[int], TimebaseMapping]:
    """
    Validate that all frame metadatas contain the same number of frames, and that the frame numbers match within each cameras' metadata.

    Args:
        frame_metadatas_by_camera: Dictionary mapping camera IDs to arrays of frame metadata.

    Raises:
        ValueError: If the number of frames is inconsistent across cameras.
    """
    num_frames = None
    for camera_id, frame_metadatas in frame_metadatas_by_camera.items():
        if num_frames is None:
            num_frames = len(frame_metadatas)
        elif len(frame_metadatas) != num_frames:
            raise ValueError(f"Camera {camera_id} has {len(frame_metadatas)} frames, expected {num_frames} frames.")

    # Check that frame numbers are consistent across cameras
    frame_numbers = []
    for frame_number in range(num_frames):
        frame_number = set([metadata[frame_number].frame_number[0] for metadata in frame_metadatas_by_camera.values()])
        if len(frame_number) != 1:
            raise ValueError(f"Inconsistent frame numbers found across cameras: {frame_number}. "
                             f"Expected all cameras to have the same frame numbers.")
        frame_numbers.append(frame_number.pop())

    camera_config_recarrays = {camera_id: config.to_numpy_record_array() for camera_id, config in
                               camera_configs.items()}
    for camera_id, metadata in frame_metadatas_by_camera.items():
        if metadata[0].camera_config != camera_config_recarrays[camera_id]:
            raise ValueError(f"Camera {camera_id} has inconsistent camera config across frames.")

    timebase_mapping_recarray: TimebaseMapping | None = None
    for camera_id, metadata in frame_metadatas_by_camera.items():
        for frame_index in range(num_frames):
            if timebase_mapping_recarray is None:
                timebase_mapping_recarray = metadata[frame_index].timebase_mapping[0]
            elif metadata[frame_index].timebase_mapping[0] != timebase_mapping_recarray:
                raise ValueError(f"Camera {camera_id} has inconsistent timebase mapping across frames.")

    logger.debug(f"Validated {len(frame_numbers)} frames across {len(frame_metadatas_by_camera)} cameras.")
    return frame_numbers, TimebaseMapping.from_numpy_record_array(timebase_mapping_recarray)


def process_and_save_recording_timestamps(
        frame_metadatas_by_camera: dict[CameraIdString, list[np.recarray]],
        camera_configs: CameraConfigs,
        recording_info: RecordingInfo,
) -> None:
    tik = time.perf_counter()
    (frame_numbers, timebase_mapping) = validate_frame_metadatas(frame_metadatas_by_camera=frame_metadatas_by_camera,
                                                                 camera_configs=camera_configs)

    # Find the earliest timestamp as recording start time
    first_timestamps = {camera_id: md[0].timestamps[0] for camera_id, md in frame_metadatas_by_camera.items()}
    recording_start_time_ns = min(
        np.min(ts.pre_frame_grab_ns) for ts in first_timestamps.values()
    )

    # Process timestamps
    (all_timestamps,
     all_durations) = process_recording_timestamps(
        frame_metadatas_by_camera=frame_metadatas_by_camera,
        frame_numbers=frame_numbers,
    )

    timestamps_rows_by_camera = create_and_save_camera_csvs(
        all_timestamps=all_timestamps,
        all_durations=all_durations,
        recording_info=recording_info,
        camera_configs=camera_configs,
        connection_frame_numbers=frame_numbers,
        recording_start_time_ns=recording_start_time_ns,
        timebase_mapping=timebase_mapping
    )
    multiframe_rows = create_and_save_multiframe_csv(timestamps_rows_by_camera=timestamps_rows_by_camera,
                                                     recording_info=recording_info,
                                                     )

    # # Save statistics summary
    # save_timestamp_statistics_summary(timestamp_stats, recording_info, frame_metadatas_by_camera)
    # logger.info(f"Successfully processed and saved timestamps for recording {recording_info.recording_name} - processed {len(frame_numbers)} frames across {len(frame_metadatas_by_camera)} cameras in {time.perf_counter() - tik:.3f} seconds.")
