import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import numpy as np

from skellycam import logger
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload, MultiFramePayload
from skellycam.models.timestamp import Timestamp


class TimestampLogger:
    def __init__(self, video_save_directory: str, camera_id: CameraId):
        self._create_timestamp_path(camera_id, video_save_directory)
        self._csv_header = ["frame_number",
                            "timestamp_from_zero_ns",
                            "frame_duration_ns",
                            "timestamp_unix_utc_ns",
                            "timestamp_utc_iso8601"]
        self._timestamp_file = self._initialize_timestamp_writer()

        self._previous_frame_timestamp: Optional[int] = None
        self._perf_counter_to_unix_mapping: Optional[Tuple[int, int]] = None
        self._first_frame_timestamp: Optional[int] = None

    def set_time_mapping(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._perf_counter_to_unix_mapping = perf_counter_to_unix_mapping
        self._first_frame_timestamp = perf_counter_to_unix_mapping[0]
        self._previous_frame_timestamp = self._first_frame_timestamp

    def log_timestamp(self, frame: FramePayload) -> Dict[str, Any]:
        timestamp_from_zero = frame.timestamp_ns - self._first_frame_timestamp
        frame_duration = frame.timestamp_ns - self._previous_frame_timestamp
        self._previous_frame_timestamp = frame.timestamp_ns

        # Convert perf_counter_ns timestamp to Unix timestamp
        start_perf_counter_time_ns, start_unix_time_ns = self._perf_counter_to_unix_mapping
        elapsed_time_ns = frame.timestamp_ns - start_perf_counter_time_ns
        unix_timestamp_ns = start_unix_time_ns + elapsed_time_ns

        # Convert Unix timestamp to ISO 8601 format
        iso8601_timestamp = datetime.fromtimestamp(unix_timestamp_ns / 1e9).isoformat()
        row_values = [frame.frame_number, timestamp_from_zero, frame_duration, unix_timestamp_ns, iso8601_timestamp]
        csv_row = ",".join([str(x) for x in row_values]) + "\n"
        self._timestamp_file.write(csv_row)
        row_dict = dict(zip(self._csv_header, row_values))
        return row_dict

    def _create_timestamp_path(self, camera_id, video_save_directory):
        video_save_directory = Path(video_save_directory)
        self._timestamp_path = Path(
            video_save_directory) / "camera_timestamps" / f"{video_save_directory.stem}_camera_{camera_id}_timestamps.csv"

    def _initialize_timestamp_writer(self):
        logger.debug(f"Creating camera timestamp file at {self._timestamp_path}")
        self._timestamp_path.parent.mkdir(parents=True, exist_ok=True)
        self._timestamp_path.touch(exist_ok=True)
        timestamp_file = open(self._timestamp_path, "w")
        timestamp_file.write(",".join(self._csv_header) + "\n")
        return timestamp_file

    def close(self):
        self._timestamp_file.close()


class TimestampLoggerManager:
    def __init__(self,
                 camera_configs: Dict[CameraId, CameraConfig],
                 video_save_directory: str):
        self._timestamp_loggers: Dict[CameraId, TimestampLogger] = {
            camera_id: TimestampLogger(video_save_directory=video_save_directory,
                                       camera_id=camera_id) for camera_id in camera_configs.keys()}
        video_path = Path(video_save_directory)
        self._make_csv_header(camera_configs)

        self._main_timestamp_path = video_path / f"{video_path.stem}_timestamps.csv"
        self._main_timestamp_file = self._initialize_main_timestamp_writer()

    def set_time_mapping(self, start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int]):
        self._save_starting_timestamp(start_time_perf_counter_ns_to_unix_mapping[1])
        self._first_frame_timestamp = start_time_perf_counter_ns_to_unix_mapping[0]
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.set_time_mapping(start_time_perf_counter_ns_to_unix_mapping)

    def _save_starting_timestamp(self, start_time_unix):
        self._starting_timestamp = Timestamp.from_utc_ns(start_time_unix)
        self._main_timestamp_path.parent.mkdir(parents=True, exist_ok=True)
        # save starting timestamp to JSON file
        with open(self._main_timestamp_path.parent / "recording_start_timestamp.json", "w") as f:
            f.write(json.dumps(self._starting_timestamp.dict(), indent=4))

    def handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        timestamp_dict_by_camera = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            timestamp_dict_by_camera[camera_id] = self._timestamp_loggers[camera_id].log_timestamp(frame=frame)
        self._log_main_timestamp(timestamp_dict_by_camera)

    def _log_main_timestamp(self, timestamp_dict_by_camera):
        row_dict = {key: None for key in self._csv_header}
        row_dict["frame_number"] = self._get_frame_number(timestamp_dict_by_camera)
        row_dict["mean_timestamp_from_zero_ns"] = self._get_mean_timestamp_from_zero_ns(timestamp_dict_by_camera)
        row_dict["mean_frame_duration_ns"] = self._get_mean_frame_duration_ns(timestamp_dict_by_camera)
        row_dict["mean_timestamp_unix_utc_ns"] = self._get_mean_timestamp_unix_utc_ns(timestamp_dict_by_camera)
        row_dict["mean_timestamp_utc_iso8601"] = self._get_mean_timestamp_utc_iso8601(
            row_dict["mean_timestamp_unix_utc_ns"])
        row_dict["inter_camera_timestamp_range_ns"] = self._get_inter_camera_timestamp_range_ns(
            timestamp_dict_by_camera)
        row_dict["inter_camera_timestamp_stddev_ns"] = self._get_inter_camera_timestamp_stddev_ns(
            timestamp_dict_by_camera)
        for camera_id, timestamp_dict in timestamp_dict_by_camera.items():
            row_dict[f"camera_{camera_id}_timestamp_log"] = str(timestamp_dict)

        row_values = [row_dict[key] for key in self._csv_header]
        csv_row = ",".join([str(x) for x in row_values]) + "\n"
        self._main_timestamp_file.write(csv_row)

    @staticmethod
    def _get_frame_number(timestamp_dict_by_camera) -> int:
        frame_numbers = [timestamp_dict["frame_number"] for timestamp_dict in timestamp_dict_by_camera.values()]
        frame_number = set(frame_numbers)
        if len(frame_number) > 1:
            logger.error(f"Frame numbers are not the same across cameras! {frame_number}")
        return frame_number.pop()

    @staticmethod
    def _get_mean_timestamp_from_zero_ns(timestamp_dict_by_camera) -> float:
        return np.mean(
            [timestamp_dict["timestamp_from_zero_ns"] for timestamp_dict in timestamp_dict_by_camera.values()])

    @staticmethod
    def _get_mean_frame_duration_ns(timestamp_dict_by_camera) -> float:
        return np.mean(
            [timestamp_dict["frame_duration_ns"] for timestamp_dict in timestamp_dict_by_camera.values()])

    @staticmethod
    def _get_mean_timestamp_unix_utc_ns(timestamp_dict_by_camera) -> float:
        return np.mean(
            [timestamp_dict["timestamp_unix_utc_ns"] for timestamp_dict in timestamp_dict_by_camera.values()])

    @staticmethod
    def _get_inter_camera_timestamp_range_ns(timestamp_dict_by_camera) -> int:
        return np.ptp(
            [timestamp_dict["timestamp_unix_utc_ns"] for timestamp_dict in timestamp_dict_by_camera.values()])

    @staticmethod
    def _get_inter_camera_timestamp_stddev_ns(timestamp_dict_by_camera) -> float:
        return np.std(
            [timestamp_dict["timestamp_unix_utc_ns"] for timestamp_dict in timestamp_dict_by_camera.values()])

    @staticmethod
    def _get_mean_timestamp_utc_iso8601(mean_unix_timestamp_ns: float):
        """
           convert mean unix timestamp to ISO 8601 format
           """
        return datetime.fromtimestamp(mean_unix_timestamp_ns / 1e9).isoformat()

    def _initialize_main_timestamp_writer(self):
        logger.debug(f"Creating main timestamp file at {self._main_timestamp_path}")
        self._main_timestamp_path.parent.mkdir(parents=True, exist_ok=True)
        self._main_timestamp_path.touch(exist_ok=True)
        timestamp_file = open(self._main_timestamp_path, "w")
        timestamp_file.write(",".join(self._csv_header) + "\n")
        return timestamp_file

    def _make_csv_header(self, camera_configs):
        self._csv_header = ["frame_number",
                            "mean_timestamp_from_zero_ns",
                            "mean_frame_duration_ns",
                            "mean_timestamp_unix_utc_ns",
                            "mean_timestamp_utc_iso8601",
                            "inter_camera_timestamp_range_ns",
                            "inter_camera_timestamp_stddev_ns",
                            ]
        for camera_id in camera_configs.keys():
            self._csv_header.append(f"camera_{camera_id}_timestamp_log")

    def close(self):
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.close()
        self._main_timestamp_file.close()
