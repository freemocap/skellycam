import numpy as np

from skellycam.core.camera_group.timestamps.recording_timestamp_stats import RecordingTimestampsStats
from skellycam.core.recorders.videos.recording_info import RecordingInfo

import logging
logger = logging.getLogger(__name__)
def save_timestamp_statistics_summary(
        multiframe_rows_recarray: np.recarray,
        recording_info: RecordingInfo,
        number_of_cameras: int,
) -> None:
    stats = RecordingTimestampsStats.from_multiframe_rows(
        multiframe_rows=multiframe_rows_recarray,
        recording_info=recording_info,
        number_of_cameras=number_of_cameras,
    )

    stats_json_path = recording_info.timestamp_stats_json_file_path

    with open(stats_json_path, 'w', encoding='utf-8') as f:
        f.write(stats.to_json())
    # logger.debug(f"Saved timestamp statistics to {stats_json_path}")

    stats_text_path = recording_info.timestamp_stats_text_file_path
    with open(stats_text_path, 'w', encoding='utf-8') as f:
        f.write(str(stats))
#     logger.debug(f"Saved timestamp statistics summary to {stats_text_path}")

    logger.success(f"Recording timestamps statistics summary:\n\n{stats}\n\n--------------------------------------------------------\n")