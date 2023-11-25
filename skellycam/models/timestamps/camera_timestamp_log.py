from datetime import datetime
from typing import Tuple

from pydantic import BaseModel, Field

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
        description="The duration of the frame, in nanoseconds since the previous frame was received by the camera group (defined as 0 on the first frame")
    timestamp_unix_utc_ns: int = Field(description="The timestamp of the frame, in nanoseconds since the Unix epoch")
    timestamp_utc_iso8601: str = Field(
        description="The timestamp of the frame, in ISO 8601 format, e.g. 2021-01-01T00:00:00.000000")

    _timestamp_mapping: Tuple[int, int] = Field(
        description="Tuple of simultaneously recorded (time.perf_counter_ns(), time.time_ns()) that maps perf_counter_ns to a unix_timestamp_ns")
    _first_frame_timestamp_ns: int = Field(
        description="Timestamp of the first frame in the recording, in nanoseconds as returned by time.perf_counter_ns()")
    _previous_frame_timestamp_ns: int = Field(
        description="Timestamp of the previous frame in the recording, in nanoseconds as returned by time.perf_counter_ns(). On the first frame, this will be a duplicate of `timestamp_from_zero_ns`")

    @classmethod
    def from_frame_payload(cls,
                           frame_payload: FramePayload,
                           timestamp_mapping: Tuple[int, int],
                           first_frame_timestamp_ns: int,
                           multi_frame_number: int,
                           previous_frame_timestamp_ns: int):

        unix_timestamp_ns = timestamp_mapping[1] + (frame_payload.timestamp_ns - timestamp_mapping[0])
        return cls(camera_id=frame_payload.camera_id,
                   multi_frame_number=multi_frame_number,
                   camera_frame_number=frame_payload.frame_number,
                   timestamp_from_zero_ns=frame_payload.timestamp_ns - first_frame_timestamp_ns,
                   frame_duration_ns=frame_payload.timestamp_ns - previous_frame_timestamp_ns,
                   timestamp_unix_utc_ns=unix_timestamp_ns,
                   timestamp_utc_iso8601=datetime.fromtimestamp(unix_timestamp_ns / 1e9).isoformat(),
                   _timestamp_mapping=timestamp_mapping,
                   _first_frame_timestamp_ns=first_frame_timestamp_ns,
                   _previous_frame_timestamp_ns=previous_frame_timestamp_ns
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
