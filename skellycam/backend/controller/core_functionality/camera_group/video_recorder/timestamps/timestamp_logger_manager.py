import json
import pprint
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any, Hashable

import pandas as pd

from skellycam.system.environment.get_logger import logger
from skellycam.backend.controller.core_functionality.camera_group.video_recorder.timestamps.timestamp_logger import \
    CameraTimestampLogger
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.models.timestamp import Timestamp
from skellycam.models.timestamps.camera_timestamp_log import CameraTimestampLog
from skellycam.models.timestamps.multi_frame_timestamp_log import MultiFrameTimestampLog


class TimestampLoggerManager:
    def __init__(self,
                 camera_configs: Dict[CameraId, CameraConfig],
                 video_save_directory: str):
        self._timestamp_logs: List[MultiFrameTimestampLog] = []
        self._start_time_perf_counter_ns_to_unix_mapping: Optional[Tuple[int, int]] = None
        self._first_frame_timestamp: Optional[int] = None
        video_path = Path(video_save_directory)
        self._file_name_prefix = video_path.stem
        self._main_timestamp_path = video_path / "timestamps"
        self._main_timestamp_path.mkdir(parents=True, exist_ok=True)
        self._timestamps_csv_path = self._main_timestamp_path / f"{self._file_name_prefix}_timestamps.csv"
        self._timestamp_loggers: Dict[CameraId, CameraTimestampLogger] = {
            camera_id: CameraTimestampLogger(main_timestamps_directory=str(self._main_timestamp_path),
                                             camera_id=camera_id) for camera_id in camera_configs.keys()}

        self._csv_header = MultiFrameTimestampLog.as_csv_header(camera_ids=list(camera_configs.keys()))

    @property
    def finished(self):
        all_loggers_finished = all([timestamp_logger.finished for timestamp_logger in self._timestamp_loggers.values()])
        timestamp_csv_exists = self._timestamps_csv_path.exists()
        timestamp_stats_exists = self._stats_path.exists()
        return all_loggers_finished and timestamp_csv_exists and timestamp_stats_exists

    def set_time_mapping(self, start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int]):
        self._start_time_perf_counter_ns_to_unix_mapping = start_time_perf_counter_ns_to_unix_mapping
        self._save_starting_timestamp(self._start_time_perf_counter_ns_to_unix_mapping)

        self._first_frame_timestamp = self._start_time_perf_counter_ns_to_unix_mapping[0]
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.set_time_mapping(self._start_time_perf_counter_ns_to_unix_mapping)

    def _save_starting_timestamp(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._starting_timestamp = Timestamp.from_mapping(perf_counter_to_unix_mapping)
        # save starting timestamp to JSON file
        with open(self._main_timestamp_path / f"{self._file_name_prefix}_recording_start_timestamp.json", "w") as f:
            f.write(json.dumps(self._starting_timestamp.to_descriptive_dict(), indent=4))

    def handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload, multi_frame_number: int):
        timestamp_log_by_camera = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            timestamp_log_by_camera[camera_id] = self._timestamp_loggers[camera_id].log_timestamp(frame=frame,
                                                                                                  multi_frame_number=multi_frame_number)
        self._log_main_timestamp(timestamp_log_by_camera,
                                 multi_frame_number=multi_frame_number)

    def _log_main_timestamp(self,
                            timestamp_log_by_camera: Dict[CameraId, CameraTimestampLog],
                            multi_frame_number: int):
        multi_frame_timestamp_log = MultiFrameTimestampLog.from_timestamp_logs(
            timestamp_logs=timestamp_log_by_camera,
            timestamp_mapping=self._start_time_perf_counter_ns_to_unix_mapping,
            first_frame_timestamp_ns=self._first_frame_timestamp,
            multi_frame_number=multi_frame_number)
        self._timestamp_logs.append(multi_frame_timestamp_log)

    def close(self):
        self._save_documentation()

        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.close()
        self._convert_to_dataframe_and_save()
        self._save_timestamp_stats()

    def _convert_to_dataframe_and_save(self):
        timestamps_dataframe = pd.DataFrame([timestamp_log.dict() for timestamp_log in self._timestamp_logs])
        timestamps_dataframe.to_csv(self._timestamps_csv_path, index=False)

    def _save_timestamp_stats(self):
        stats = self._get_timestamp_stats()
        self._stats_path = self._main_timestamp_path / f"{self._file_name_prefix}_timestamp_stats.json"
        stats["timestamp_stats_by_camera_id"] = self._get_camera_stats(stats)

        with open(self._stats_path, "w") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(f"Saved multi-frame timestamp stats to {self._stats_path} -\n\n"
                    f"{pprint.pformat(stats, indent=4)})\n\n")

    def _get_camera_stats(self, stats) -> Dict[Hashable, Dict[str, float]]:
        camera_stats_by_id = {}
        try:
            for camera_id, timestamp_logger in self._timestamp_loggers.items():
                if timestamp_logger.stats is None:
                    raise AssertionError(
                        "Timestamp logger stats are None, but `close` was called! Theres a buggo in the logic somewhere...")
                camera_stats_by_id[camera_id] = timestamp_logger.stats

        except Exception as e:
            logger.error(f"Error saving timestamp stats: {e}")
            raise e
        return camera_stats_by_id

    def _get_timestamp_stats(self) -> Dict[Hashable, Any]:
        stats = {"total_frames": len(self._timestamp_logs),
                 "total_recording_duration_s": self._timestamp_logs[-1].mean_timestamp_from_zero_s,
                 "start_time_perf_counter_ns_to_unix_mapping": {
                     "time.perf_counter_ns": self._start_time_perf_counter_ns_to_unix_mapping[0],
                     "time.time_ns": self._start_time_perf_counter_ns_to_unix_mapping[1]}
                 }
        stats.update(self._get_stats_from_csv())
        return stats

    def _get_stats_from_csv(self) -> Dict[str, float]:
        csv_data_frame = pd.read_csv(self._timestamps_csv_path)
        return {"mean_frame_duration_s": csv_data_frame["mean_frame_duration_s"].mean(),
                "std_frame_duration_s": csv_data_frame["mean_frame_duration_s"].std(),
                "mean_frames_per_second": csv_data_frame["mean_frame_duration_s"].mean() ** -1,
                "mean_inter_camera_timestamp_range_s": csv_data_frame["inter_camera_timestamp_range_s"].mean(),
                "std_dev_inter_camera_timestamp_range_s": csv_data_frame["inter_camera_timestamp_range_s"].std(),
                "mean_inter_camera_timestamp_stddev_s": csv_data_frame["inter_camera_timestamp_stddev_s"].mean(),
                "std_dev_inter_camera_timestamp_stddev_s": csv_data_frame["inter_camera_timestamp_stddev_s"].std()}

    def _save_documentation(self):
        documentation_path = self._main_timestamp_path / "timestamps_field_descriptions.md"
        if not documentation_path.exists():
            with open(documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())
