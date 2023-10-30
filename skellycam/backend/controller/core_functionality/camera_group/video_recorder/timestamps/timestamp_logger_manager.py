import json
from pathlib import Path
from typing import Dict, Optional, Tuple

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

        self._main_timestamp_file.write(multi_frame_timestamp_log.to_csv_row())

    def _initialize_main_timestamp_writer(self):
        logger.debug(f"Creating main timestamp file at {self._csv_path}")
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_path.touch(exist_ok=True)
        timestamp_file = open(self._csv_path, "w")
        timestamp_file.write(self._csv_header)
        return timestamp_file

    def close(self):
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.close()
        self._save_documentation()
        self._main_timestamp_file.close()

    def _save_documentation(self):
        documentation_path = self._main_timestamp_path / "timestamps_field_descriptions.md"
        if not documentation_path.exists():
            with open(documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())
