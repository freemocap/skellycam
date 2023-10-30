import json
import pprint
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import numpy as np

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.video_recorder.timestamps.timestamp_logger import \
    CameraTimestampLogger, MultiFrameTimestampLog, CameraTimestampLog
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.models.timestamp import Timestamp


class TimestampLoggerManager:
    def __init__(self,
                 camera_configs: Dict[CameraId, CameraConfig],
                 video_save_directory: str):
        self._timestamp_logs: List[MultiFrameTimestampLog] = []
        self._timestamp_mapping: Optional[Tuple[int, int]] = None
        self._first_frame_timestamp: Optional[int] = None
        video_path = Path(video_save_directory)
        self._main_timestamp_path = video_path / "timestamps"
        self._csv_path = self._main_timestamp_path / f"{video_path.stem}_timestamps.csv"
        self._timestamp_loggers: Dict[CameraId, CameraTimestampLogger] = {
            camera_id: CameraTimestampLogger(main_timestamps_directory=str(self._main_timestamp_path),
                                             camera_id=camera_id) for camera_id in camera_configs.keys()}

        self._csv_header = MultiFrameTimestampLog.as_csv_header(camera_ids=list(camera_configs.keys()))

        self._main_timestamp_file = self._initialize_main_timestamp_writer()

    @property
    def finished(self):
        return all([timestamp_logger.finished for timestamp_logger in self._timestamp_loggers.values()])

    def set_time_mapping(self, start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int]):
        self._timestamp_mapping = start_time_perf_counter_ns_to_unix_mapping
        self._save_starting_timestamp(self._timestamp_mapping)

        self._first_frame_timestamp = self._timestamp_mapping[0]
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.set_time_mapping(self._timestamp_mapping)

    def _save_starting_timestamp(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._starting_timestamp = Timestamp.from_mapping(perf_counter_to_unix_mapping)
        self._main_timestamp_path.parent.mkdir(parents=True, exist_ok=True)
        # save starting timestamp to JSON file
        with open(self._main_timestamp_path / "recording_start_timestamp.json", "w") as f:
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
            timestamp_mapping=self._timestamp_mapping,
            first_frame_timestamp_ns=self._first_frame_timestamp,
            multi_frame_number=multi_frame_number)
        self._timestamp_logs.append(multi_frame_timestamp_log)
        self._main_timestamp_file.write(multi_frame_timestamp_log.to_csv_row())

    def _initialize_main_timestamp_writer(self):
        logger.debug(f"Creating main timestamp file at {self._csv_path}")
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_path.touch(exist_ok=True)
        timestamp_file = open(self._csv_path, "w")
        timestamp_file.write(self._csv_header)
        return timestamp_file

    def close(self):
        self._save_documentation()
        self._save_timestamp_stats()

        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.close()
        self._main_timestamp_file.close()

    def _save_timestamp_stats(self):
        stats = self._get_timestamp_stats()
        stats_path = self._main_timestamp_path / "timestamp_stats.json"
        with open(stats_path, "w") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(f"Saved multiframe timestamp stats to {stats_path} -\n\n"
                    f"{pprint.pformat(stats, indent=4)})\n\n")

    def _get_timestamp_stats(self):
        stats = {}
        frames_per_second = {}
        stats["frames_per_second"] = frames_per_second
        frames_per_second["mean"] = np.mean(self._get_frame_durations()) ** -1
        frames_per_second["std"] = np.std(self._get_frame_durations()) ** -1
        frames_per_second["min"] = np.min(self._get_frame_durations()) ** -1
        frames_per_second["max"] = np.max(self._get_frame_durations()) ** -1

        frame_duration_s = {}
        stats["frame_duration"] = frame_duration_s
        frame_duration_s["mean"] = np.mean(self._get_frame_durations())
        frame_duration_s["std"] = np.std(self._get_frame_durations())
        frame_duration_s["min"] = np.min(self._get_frame_durations())
        frame_duration_s["max"] = np.max(self._get_frame_durations())

        inter_camera_timestamp_range_s = {}
        stats["inter_camera_timestamp_range_s"] = inter_camera_timestamp_range_s
        inter_camera_timestamp_range_s["mean"] = np.mean(
            [timestamp_log.inter_camera_timestamp_range_s for timestamp_log in self._timestamp_logs])
        inter_camera_timestamp_range_s["std"] = np.std(
            [timestamp_log.inter_camera_timestamp_range_s for timestamp_log in self._timestamp_logs])
        inter_camera_timestamp_range_s["min"] = np.min(
            [timestamp_log.inter_camera_timestamp_range_s for timestamp_log in self._timestamp_logs])
        inter_camera_timestamp_range_s["max"] = np.max(
            [timestamp_log.inter_camera_timestamp_range_s for timestamp_log in self._timestamp_logs])

        inter_camera_timestamp_stddev_s = {}
        stats["inter_camera_timestamp_stddev_s"] = inter_camera_timestamp_stddev_s
        inter_camera_timestamp_stddev_s["mean"] = np.mean(
            [timestamp_log.inter_camera_timestamp_stddev_s for timestamp_log in self._timestamp_logs])
        inter_camera_timestamp_stddev_s["std"] = np.std(
            [timestamp_log.inter_camera_timestamp_stddev_s for timestamp_log in self._timestamp_logs])
        inter_camera_timestamp_stddev_s["min"] = np.min(
            [timestamp_log.inter_camera_timestamp_stddev_s for timestamp_log in self._timestamp_logs])
        inter_camera_timestamp_stddev_s["max"] = np.max(
            [timestamp_log.inter_camera_timestamp_stddev_s for timestamp_log in self._timestamp_logs])

        return stats

    def _get_frame_durations(self) -> List[int]:
        durations = [0]
        for index in range(len(self._timestamp_logs) - 1):
            current_frame_timestamp = self._timestamp_logs[index].mean_timestamp_from_zero_s
            next_frame_timestamp = self._timestamp_logs[index + 1].mean_timestamp_from_zero_s
            frame_duration = next_frame_timestamp - current_frame_timestamp
            durations.append(frame_duration)
        return durations

    def _save_documentation(self):
        documentation_path = self._main_timestamp_path / "timestamps_field_descriptions.md"
        if not documentation_path.exists():
            with open(documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())
