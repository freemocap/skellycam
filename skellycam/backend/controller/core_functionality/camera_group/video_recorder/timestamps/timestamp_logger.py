import json
import pprint
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from typing import Tuple, Dict

import numpy as np
from pydantic import BaseModel, Field

from skellycam import logger
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class CameraTimestampLog(BaseModel):
    camera_id: CameraId = Field(description="Camera ID of the camera that recorded the frame")
    multi_frame_number: int = Field(
        description="The number of multi-frame payloads that have been received by the camera group, will be the same for all cameras and corresponds to the frame number in saved videos")
    camera_frame_number: int = Field(
        description="The number of frames that have been received by the camera since it was started (NOTE, this won't match the other cameras or the frame number in saved videos)")
    timestamp_from_zero_ns: int = Field(
        description="The timestamp of the frame, in nanoseconds since the first frame was received by the camera group")
    frame_duration_ns: int = Field(
        description="The duration of the frame, in nanoseconds since the previous frame was received by the camera group")
    timestamp_unix_utc_ns: int = Field(description="The timestamp of the frame, in nanoseconds since the Unix epoch")
    timestamp_utc_iso8601: str = Field(
        description="The timestamp of the frame, in ISO 8601 format, e.g. 2021-01-01T00:00:00.000000")

    _timestamp_mapping: Tuple[int, int] = Field(
        description="Tuple of simultaneously recorded (time.perf_counter_ns(), time.time_ns()) that maps perf_counter_ns to a unix_timestamp_ns")
    _first_frame_timestamp_ns: int = Field(
        description="Timestamp of the first frame in the recording, in nanoseconds as returned by time.perf_counter_ns()")

    @classmethod
    def from_frame_payload(cls, frame_payload: FramePayload, timestamp_mapping: Tuple[int, int],
                           first_frame_timestamp_ns: int, multi_frame_number: int):
        return cls(camera_id=frame_payload.camera_id,
                   multi_frame_number=multi_frame_number,
                   camera_frame_number=frame_payload.frame_number,
                   timestamp_from_zero_ns=frame_payload.timestamp_ns - first_frame_timestamp_ns,
                   frame_duration_ns=frame_payload.timestamp_ns - timestamp_mapping[0],
                   timestamp_unix_utc_ns=frame_payload.timestamp_ns,
                   timestamp_utc_iso8601=datetime.fromtimestamp(frame_payload.timestamp_ns / 1e9).isoformat(),
                   _timestamp_mapping=timestamp_mapping,
                   _first_frame_timestamp_ns=first_frame_timestamp_ns
                   )

    @classmethod
    def as_csv_header(cls) -> str:
        return ",".join(cls.__fields__.keys()) + "\n"

    def to_csv_row(self):
        return ",".join([str(x) for x in self.dict().values()]) + "\n"

    @classmethod
    def to_document(cls) -> str:
        """
        Prints the description of each field in the class in a nice markdown format
        """
        document = "# Camera Timestamp Log Field Descriptions:\n"
        document += f"The following fields are included in the camera timestamp log, as defined in the {cls.__class__.__name__} data model/class:\n"
        for field_name, field in cls.__fields__.items():
            document += f"- **{field_name}**:\n\n {field.field_info.description}\n\n"
            if field_name.startswith("_"):
                document += f"    - note, this is a private field and is not included in the CSV output. You can find it in the `recording_start_timestamp.json` file in the recording folder\n"
        return document


class MultiFrameTimestampLog(BaseModel):
    multi_frame_number: int = Field(
        description="The number of multi-frame payloads that have been received by the camera group, "
                    "will be the same for all cameras and corresponds to the frame number in saved videos")
    mean_timestamp_from_zero_s: float = Field(
        description="The mean timestamp of the individual frames in this multi-frame, in seconds since the first frame was received by the camera group")
    mean_frame_duration_s: float = Field(
        description="The mean duration of the multi-frame, in seconds since the previous frame was received by the camera group")
    mean_timestamp_unix_utc_s: float = Field(
        description="The mean timestamp of the frames in this multi-frame, in seconds since the Unix epoch")
    mean_timestamp_utc_iso8601: str = Field(
        description="The mean timestamp of the multi-frame, made by converting `mean_timestamp_unix_utc_s` in ISO 8601 format, e.g. 2021-01-01T00:00:00.000000")
    inter_camera_timestamp_range_s: float = Field(
        description="The range of timestamps between cameras, in seconds")
    inter_camera_timestamp_stddev_s: float = Field(
        description="The standard deviation of timestamps between cameras, in seconds")

    camera_logs: Dict[CameraId, CameraTimestampLog] = Field(
        description="Individual CameraTimestampLog objects for each camera in the multi-frame")

    _timestamp_mapping: Tuple[int, int] = Field(
        description="Tuple of simultaneously recorded (time.perf_counter_ns(), time.time_ns()) that maps perf_counter_ns to a unix_timestamp_ns")
    _first_frame_timestamp_ns: int = Field(
        description="Timestamp of the first frame in the recording, in nanoseconds as returned by time.perf_counter_ns()")

    @classmethod
    def from_timestamp_logs(cls, timestamp_logs: Dict[CameraId, CameraTimestampLog], timestamp_mapping: Tuple[int, int],
                            first_frame_timestamp_ns: int, multi_frame_number: int):
        return cls(multi_frame_number=multi_frame_number,
                   mean_timestamp_from_zero_s=np.mean(
                       [timestamp_log.timestamp_from_zero_ns for timestamp_log in timestamp_logs.values()]) / 1e9,
                   mean_frame_duration_s=np.mean(
                       [timestamp_log.frame_duration_ns for timestamp_log in timestamp_logs.values()]) / 1e9,
                   mean_timestamp_unix_utc_s=np.mean(
                       [timestamp_log.timestamp_unix_utc_ns for timestamp_log in timestamp_logs.values()]) / 1e9,
                   mean_timestamp_utc_iso8601=datetime.fromtimestamp(np.mean(
                       [timestamp_log.timestamp_unix_utc_ns for timestamp_log in
                        timestamp_logs.values()]) / 1e9).isoformat(),
                   inter_camera_timestamp_range_s=np.ptp(
                       [timestamp_log.timestamp_unix_utc_ns for timestamp_log in timestamp_logs.values()]),
                   inter_camera_timestamp_stddev_s=np.std(
                       [timestamp_log.timestamp_unix_utc_ns for timestamp_log in timestamp_logs.values()]),
                   camera_logs=timestamp_logs,
                   _timestamp_mapping=timestamp_mapping,
                   _first_frame_timestamp_ns=first_frame_timestamp_ns
                   )

    @classmethod
    def as_csv_header(cls, camera_ids: List[CameraId]) -> str:
        column_names = list(cls.__fields__.keys())
        column_names.remove("camera_logs")
        for camera_id in camera_ids:
            column_names.append(f"camera_{camera_id}_log")
        return ",".join(column_names) + "\n"

    def to_csv_row(self) -> str:
        row_dict = self.dict(exclude={"camera_logs"})
        row_dict["camera_logs"] = ",".join([str(camera_log.dict()) for camera_log in self.camera_logs.values()])
        return ",".join([str(value) for value in row_dict.values()]) + "\n"

    @classmethod
    def to_document(cls) -> str:
        """
        Prints the description of each field in the class in a nice markdown format
        """
        document = "# Main Timestamp Log Field Descriptions:\n"
        document += f"The following fields are included in the main timestamp log, as defined in the {cls.__class__.__name__} data model/class:\n"
        for field_name, field in cls.__fields__.items():
            document += f"- **{field_name}**:\n\n {field.field_info.description}\n\n"
            if field_name.startswith("_"):
                document += f"    - note, this is a private field and is not included in the CSV output. You can find it in the `recording_start_timestamp.json` file in the recording folder\n"
        return document


class CameraTimestampLogger:
    def __init__(self, main_timestamps_directory: str, camera_id: CameraId):
        self._create_timestamp_path(camera_id, main_timestamps_directory)
        self._csv_header = CameraTimestampLog.as_csv_header()
        self._timestamp_file = self._initialize_timestamp_writer()

        self._previous_frame_timestamp: Optional[int] = None
        self._perf_counter_to_unix_mapping: Optional[Tuple[int, int]] = None
        self._first_frame_timestamp: Optional[int] = None

    @property
    def finished(self):
        return self._timestamp_file.closed and Path(self._csv_path).exists()

    def set_time_mapping(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._perf_counter_to_unix_mapping = perf_counter_to_unix_mapping
        self._first_frame_timestamp = perf_counter_to_unix_mapping[0]
        self._previous_frame_timestamp = self._first_frame_timestamp

    def log_timestamp(self, multi_frame_number: int, frame: FramePayload) -> CameraTimestampLog:
        log = CameraTimestampLog.from_frame_payload(frame_payload=frame,
                                                    timestamp_mapping=self._perf_counter_to_unix_mapping,
                                                    first_frame_timestamp_ns=self._first_frame_timestamp,
                                                    multi_frame_number=multi_frame_number)
        self._timestamp_file.write(log.to_csv_row())
        return log

    def _create_timestamp_path(self, camera_id: CameraId, save_directory: str):
        camera_timestamps_path = Path(save_directory) / "camera_timestamps"
        self._csv_path = camera_timestamps_path / f"{Path(save_directory).stem}_camera_{camera_id}_timestamps.csv"

    def _initialize_timestamp_writer(self):
        logger.debug(f"Creating camera timestamp file at {self._csv_path}")
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_path.touch(exist_ok=True)
        timestamp_file = open(self._csv_path, "w")
        timestamp_file.write(self._csv_header)
        return timestamp_file

    def _save_documentation(self):
        documentation_path = self._csv_path.parent.parent / "camera_timestamps_field_descriptions.md"
        if not documentation_path.exists():
            with open(documentation_path, "w") as f:
                f.write(CameraTimestampLog.to_document())

    def close(self):
        self._save_documentation()
        self._save_timestamp_stats()
        self._timestamp_file.close()

    def _save_timestamp_stats(self):
        stats = self._get_timestamp_stats()
        stats_path = self._csv_path.parent / "camera_timestamps_stats.json"
        with open(stats_path, "w") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(f"Saved timestamp stats to {stats_path} -\n\n"
                    f"{pprint.pformat(stats, indent=4)})\n\n")

    def _get_timestamp_stats(self):
        stats = {}
        stats.update({
            "first_frame_timestamp_ns": self._first_frame_timestamp,
            "perf_counter_to_unix_mapping_ns": self._perf_counter_to_unix_mapping,
        })
        stats.update(self._get_stats_from_csv())

        return stats

    def _get_stats_from_csv(self):
        csv = np.genfromtxt(self._csv_path, delimiter=",", names=True)
        stats = {}
        for field_name in csv.dtype.names:
            stats[field_name] = {}
            stats[field_name]["mean"] = np.mean(csv[field_name])
            stats[field_name]["std"] = np.std(csv[field_name])
            stats[field_name]["min"] = np.min(csv[field_name])
            stats[field_name]["max"] = np.max(csv[field_name])
        return stats
