from datetime import datetime
from typing import Tuple, Dict, List

import numpy as np
from pydantic import BaseModel, Field

from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.timestamps.camera_timestamp_log import CameraTimestampLog


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
        timestamps_per_camera = [timestamp_log.timestamp_unix_utc_ns / 1e9 for timestamp_log in timestamp_logs.values()]
        inter_camera_timestamp_range_s = np.max(timestamps_per_camera) - np.min(timestamps_per_camera)
        inter_camera_timestamp_stddev_s = np.std(timestamps_per_camera)

        return cls(multi_frame_number=multi_frame_number,
                   mean_timestamp_from_zero_s=np.mean(
                       [timestamp_log.timestamp_from_zero_ns for timestamp_log in timestamp_logs.values()]) / 1e9,
                   mean_frame_duration_s=np.mean(
                       [timestamp_log.frame_duration_ns for timestamp_log in timestamp_logs.values()]) / 1e9,
                   mean_timestamp_unix_utc_s=np.mean(
                       [timestamp_log.timestamp_unix_utc_ns for timestamp_log in timestamp_logs.values()]) / 1e9,
                   mean_timestamp_utc_iso8601=datetime.fromtimestamp(np.mean(
                       [timestamp_log.timestamp_unix_utc_ns / 1e9 for timestamp_log in
                        timestamp_logs.values()])).isoformat(),
                   inter_camera_timestamp_range_s=inter_camera_timestamp_range_s,
                   inter_camera_timestamp_stddev_s=inter_camera_timestamp_stddev_s,
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
