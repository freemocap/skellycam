from datetime import datetime

from pydantic import BaseModel, Field

from skellycam.core.frame_payloads.metadata.frame_metadata import FrameMetadata, FrameLifespanTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimeBaseMapping
from skellycam.core.types import CameraIndex


class CameraTimestampLog(BaseModel):

    camera_id: CameraIndex = Field(
        description="- Camera ID of the camera that recorded the frame"
    )
    frame_number: int = Field(
        description="- The number of frame payloads that have been received by the camera group, will be the same for all cameras and corresponds to the frame number in saved videos"
    )
    timestamp_from_zero_s: float = Field(
        description="- The timestamp of the frame, in nanoseconds since the first frame was received by the camera group"
    )
    timestamp_perf_counter_ns: int = Field(
        description="- The timestamp of the frame, in nanoseconds as returned by time.perf_counter_ns() - this is the most accurate timestamp available, and is the timestamp returned in `FramePayload`"
    )
    timestamp_utc_ns: int = Field(
        description="- The timestamp of the frame, in nanoseconds since the Unix epoch (1970-01-01 00:00:00 UTC/GMT)"
    )
    timestamp_utc_iso8601: str = Field(
        description="- The timestamp of the frame, in ISO 8601 format, in UTC/GMT timezone e.g. 2021-01-01T00:00:00.000000"
    )
    timestamp_local_ns: int = Field(
        description="- The timestamp of the frame, in nanoseconds since the Unix epoch in local time (1970-01-01 00:00:00 GMT-local time offset)"
    )
    timestamp_local_iso8601: str = Field(
        description="- The timestamp of the frame, in ISO 8601 format in local time timezone, e.g. 2021-01-01T00:00:00.000000"
    )
    frame_lifespan: FrameLifespanTimestamps

    @classmethod
    def from_frame_metadata(
            cls,
            frame_metadata: FrameMetadata,
            first_frame_metadata: FrameMetadata,
            timebase_mapping: TimeBaseMapping
    ):


        return cls(
            camera_id=frame_metadata.camera_id,
            frame_number=frame_metadata.frame_number,
            timestamp_perf_counter_ns=frame_metadata.timestamp_ns,
            timestamp_from_zero_s=frame_metadata.timestamp_ns- first_frame_metadata.timestamp_ns / 1e9,
            timestamp_utc_ns=timebase_mapping.convert_perf_counter_ns_to_unix_ns(frame_metadata.timestamp_ns,local_time=False),
            timestamp_utc_iso8601=datetime.fromtimestamp(
                timebase_mapping.convert_perf_counter_ns_to_unix_ns(frame_metadata.timestamp_ns,local_time=False) / 1e9
            ).isoformat(),
            timestamp_local_ns=timebase_mapping.convert_perf_counter_ns_to_unix_ns(frame_metadata.timestamp_ns,local_time=True),
            timestamp_local_iso8601=datetime.fromtimestamp(
                timebase_mapping.convert_perf_counter_ns_to_unix_ns(frame_metadata.timestamp_ns,local_time=True) / 1e9
            ).isoformat(),
            frame_lifespan=frame_metadata.frame_lifespan_timestamps
        )




    @classmethod
    def to_document(cls) -> str:
        """
        Prints the description of each field in the class in a nice markdown format
        """
        document = "# Individual Camera Timestamp Log Field Descriptions:\n"
        document += f"The following fields are included in the camera timestamp log, as defined in the {cls.__class__.__name__} data model/class:\n"
        for field_name, field in cls.__fields__.items():
            document += f"- **{field_name}**:{field.description}\n\n"
            if field_name.startswith("_"):
                document += f"    - note, this is a private field and is not included in the CSV output. You can find it in the `recording_start_timestamp.json` file in the recording folder\n"
        return document


