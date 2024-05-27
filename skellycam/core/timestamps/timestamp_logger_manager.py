import json
import logging
import pprint
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any, Hashable

import polars as pl

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.timestamps.camera_timestamp_log import CameraTimestampLog
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.core.timestamps.multi_frame_timestamp_log import (
    MultiFrameTimestampLog,
)
from skellycam.core.timestamps.timestamp_logger import (
    CameraTimestampLogger,
)

logger = logging.getLogger(__name__)


class TimestampLoggerManager:
    def __init__(self, camera_configs: CameraConfigs, video_save_directory: str):
        self._multi_frame_timestamp_logs: List[MultiFrameTimestampLog] = []

        self._start_time_perf_counter_ns_to_unix_mapping: Optional[
            Tuple[int, int]
        ] = None

        self._first_frame_timestamp: Optional[int] = None

        self._create_save_paths(video_save_directory)

        self._timestamp_loggers: Dict[CameraId, CameraTimestampLogger] = {
            camera_id: CameraTimestampLogger(
                main_timestamps_directory=str(self._main_timestamp_path),
                camera_id=camera_id,
            )
            for camera_id in camera_configs.keys()
        }

        self._csv_header = MultiFrameTimestampLog.as_csv_header(
            camera_ids=list(camera_configs.keys())
        )

    @property
    def log_counts(self) -> Dict[CameraId, int]:
        return {
            camera_id: timestamp_logger.log_count
            for camera_id, timestamp_logger in self._timestamp_loggers.items()
        }

    def to_dataframe(self) -> pl.DataFrame:
        df = pl.DataFrame(
            [timestamp_log.model_dump() for timestamp_log in self._multi_frame_timestamp_logs]
        )
        return df

    def check_if_finished(self):
        all_loggers_finished = all(
            [
                timestamp_logger.check_if_finished()
                for timestamp_logger in self._timestamp_loggers.values()
            ]
        )
        timestamp_csv_exists = self._timestamps_csv_path.exists()
        timestamp_stats_exists = self._stats_path.exists()
        return all_loggers_finished and timestamp_csv_exists and timestamp_stats_exists

    def set_time_mapping(
        self, start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int]
    ):
        logger.debug(
            f"Setting (`perf_coutner_ns`:`unix_time_ns`) time mapping: {start_time_perf_counter_ns_to_unix_mapping}..."
        )
        self._start_time_perf_counter_ns_to_unix_mapping = (
            start_time_perf_counter_ns_to_unix_mapping
        )
        self._save_starting_timestamp(self._start_time_perf_counter_ns_to_unix_mapping)

        self._first_frame_timestamp = self._start_time_perf_counter_ns_to_unix_mapping[
            0
        ]
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.set_time_mapping(
                self._start_time_perf_counter_ns_to_unix_mapping
            )

    def handle_multi_frame_payload(
        self, multi_frame_payload: MultiFramePayload, multi_frame_number: int
    ):
        timestamp_log_by_camera = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            timestamp_log_by_camera[camera_id] = self._timestamp_loggers[
                camera_id
            ].log_timestamp(frame=frame, multi_frame_number=multi_frame_number)
        self._log_main_timestamp(
            timestamp_log_by_camera, multi_frame_number=multi_frame_number
        )

    def close(self):
        logger.debug(
            f"Closing timestamp logger manager with {len(self._multi_frame_timestamp_logs)} multi-frame logs and {self.log_counts} per-camera logs..."
        )

        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.close()

        self._save_documentation()
        self._convert_to_dataframe_and_save()
        self._save_timestamp_stats()
        if not self.check_if_finished():
            raise AssertionError(
                "Failed to save timestamp logs for all cameras to CSV and JSON files!"
            )

        logger.success("Timestamp logs saved successfully!")

    def _save_starting_timestamp(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._starting_timestamp = FullTimestamp.from_perf_to_unix_mapping(perf_counter_to_unix_mapping)
        # save starting timestamp to JSON file
        with open(
            self._starting_timestamp_json_path,
            "w",
        ) as f:
            f.write(
                json.dumps(self._starting_timestamp.to_descriptive_dict(), indent=4)
            )

    def _log_main_timestamp(
        self,
        timestamp_log_by_camera: Dict[CameraId, CameraTimestampLog],
        multi_frame_number: int,
    ):
        multi_frame_timestamp_log = MultiFrameTimestampLog.from_timestamp_logs(
            timestamp_logs=timestamp_log_by_camera,
            timestamp_mapping=self._start_time_perf_counter_ns_to_unix_mapping,
            first_frame_timestamp_ns=self._first_frame_timestamp,
            multi_frame_number=multi_frame_number,
        )
        self._multi_frame_timestamp_logs.append(multi_frame_timestamp_log)

    def _convert_to_dataframe_and_save(self):
        df = self.to_dataframe()
        df.to_csv(self._timestamps_csv_path, index=False)
        logger.info(
            f"Saved multi-frame timestamp logs to {self._timestamps_csv_path} \n\n"
            f"Total frames: {len(self._multi_frame_timestamp_logs)}\n\n"
            f"First/last 5 frames:\n\n"
            f"{df.head()}\n\n...\n\n{df.tail()}"
        )

    def _save_timestamp_stats(self):
        stats = self._get_timestamp_stats()

        stats["timestamp_stats_by_camera_id"] = self._get_camera_stats(stats)

        with open(self._stats_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(
            f"Saved multi-frame timestamp stats to {self._stats_path} -\n\n"
            f"{pprint.pformat(stats, indent=4)})\n\n"
        )

    def _get_camera_stats(self, stats) -> Dict[Hashable, Dict[str, float]]:
        camera_stats_by_id = {}
        try:
            for camera_id, timestamp_logger in self._timestamp_loggers.items():
                if timestamp_logger.stats is None:
                    raise AssertionError(
                        "Timestamp logger stats are None, but `close` was called! Theres a buggo in the logic somewhere..."
                    )
                camera_stats_by_id[camera_id] = timestamp_logger.stats

        except Exception as e:
            logger.error(f"Error saving timestamp stats: {e}")
            raise e
        return camera_stats_by_id

    def _get_timestamp_stats(self) -> Dict[Hashable, Any]:
        stats = {
            "total_frames": len(self._multi_frame_timestamp_logs),
            "total_recording_duration_s": self._multi_frame_timestamp_logs[
                -1
            ].mean_timestamp_from_zero_s,
            "start_time_perf_counter_ns_to_unix_mapping": {
                "time.perf_counter_ns": self._start_time_perf_counter_ns_to_unix_mapping[
                    0
                ],
                "time.time_ns": self._start_time_perf_counter_ns_to_unix_mapping[1],
            },
        }
        stats.update(self._calculate_stats())
        return stats

    def _calculate_stats(self) -> Dict[str, float]:
        df = self.to_dataframe()  # get the dataframe to avoid recalculating
        return {
            "mean_frame_duration_s": df["mean_frame_duration_s"].mean(),
            "std_frame_duration_s": df["mean_frame_duration_s"].std(),
            "mean_frames_per_second": df["mean_frame_duration_s"].mean() ** -1,
            "mean_inter_camera_timestamp_range_s": df[
                "inter_camera_timestamp_range_s"
            ].mean(),
            "std_dev_inter_camera_timestamp_range_s": df[
                "inter_camera_timestamp_range_s"
            ].std(),
            "mean_inter_camera_timestamp_stddev_s": df[
                "inter_camera_timestamp_stddev_s"
            ].mean(),
            "std_dev_inter_camera_timestamp_stddev_s": df[
                "inter_camera_timestamp_stddev_s"
            ].std(),
        }

    def _save_documentation(self):
        if not self._documentation_path.exists():
            with open(self._documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())

        logger.info(
            f"Saved multi_frame_timestamp descriptions to {self._documentation_path}"
        )

    def _create_save_paths(self, video_save_directory):
        video_path = Path(video_save_directory)

        self._file_name_prefix = video_path.stem
        self._main_timestamp_path = video_path / "timestamps"
        self._main_timestamp_path.mkdir(parents=True, exist_ok=True)
        self._timestamps_csv_path = (
            self._main_timestamp_path / f"{self._file_name_prefix}_timestamps.csv"
        )

        self._starting_timestamp_json_path = (
            self._main_timestamp_path
            / f"{self._file_name_prefix}_recording_start_timestamp.json"
        )

        self._documentation_path = (
            self._main_timestamp_path / f"{self._file_name_prefix}_documentation.txt"
        )

        self._stats_path = (
            self._main_timestamp_path / f"{self._file_name_prefix}_timestamp_stats.json"
        )
