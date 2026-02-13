from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from skellycam.core.camera_group.timestamps.frame_timestamps import FrameTimestamps
from skellycam.utilities.time_unit_conversion import ns_to_ms, ns_to_sec

if TYPE_CHECKING:
    from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping




class FrameTimestampsCSVRow(BaseModel):
    recording_frame_number: int
    connection_frame_number: int

    # Timestamp fields
    from_recording_start_sec: float = Field(serialization_alias="timestamp.from_recording_start.sec")
    utc_sec: float = Field(serialization_alias="timestamp.utc.seconds")
    local_iso8601: str = Field(serialization_alias="timestamp.local.iso8601")
    perf_counter_ns: int = Field(serialization_alias="timestamp.perf_counter_ns.ns")

    # From-previous measures (i.e. frame duration and framerate, which require knowledge of the previous frame)
    frame_duration_ms: float | None = Field(serialization_alias="from_previous.frame_duration.ms")
    framerate_hz: float | None = Field(serialization_alias="from_previous.framerate.hz")

    # Lifespan timestamp fields
    initialized_ns: int = Field(serialization_alias="frame.initialized.ns")
    pre_grab_ns: int = Field(serialization_alias="frame.pre_grab.ns")
    post_grab_ns: int = Field(serialization_alias="frame.post_grab.ns")
    pre_retrieve_ns: int = Field(serialization_alias="frame.pre_retrieve.ns")
    post_retrieve_ns: int = Field(serialization_alias="frame.post_retrieve.ns")
    pre_record_frame_ns: int = Field(serialization_alias="frame.pre_record_frame.ns")
    post_record_frame_ns: int = Field(serialization_alias="frame.post_record_frame.ns")
    pre_copy_to_camera_shm_ns: int = Field(serialization_alias="frame.pre_copy_to_camera_shm.ns")
    post_copy_to_camera_shm_ns: int = Field(serialization_alias="frame.post_copy_to_camera_shm.ns")

    # Lifespan duration fields
    during_frame_grab_ns: int = Field(serialization_alias="duration.during_frame_grab.ns")
    idle_before_retrieve_ns: int = Field(serialization_alias="duration.idle_before_retrieve.ns")
    during_frame_retrieve_ns: int = Field(serialization_alias="duration.during_frame_retrieve.ns")
    idle_before_copy_to_camera_shm_ns: int = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.ns")
    during_copy_to_camera_shm_ns: int = Field(serialization_alias="duration.during_copy_to_camera_shm.ns")
    idle_before_frame_record_ns: int = Field(serialization_alias="duration.idle_before_frame_record.ns")
    during_frame_record_ns: int = Field(serialization_alias="duration.during_frame_record.ns")

    total_camera_idle_time_ns: int = Field(serialization_alias="duration.idle_before_grab.ns")
    total_frame_processing_time_ns: int = Field(serialization_alias="total.frame_processing_time.ns")

    @classmethod
    def from_frame_timestamps(cls,
                              frame_timestamps: FrameTimestamps,
                              recording_frame_number: int,
                              connection_frame_number: int,
                              recording_start_time_ns: int,
                              previous_frame_timestamps: FrameTimestamps | None = None,
                              ) -> "FrameTimestampsCSVRow":
        timebase: TimebaseMapping = frame_timestamps.timebase_mapping

        frame_duration_ms = ns_to_ms(
            frame_timestamps.timestamp_ns - previous_frame_timestamps.timestamp_ns) if previous_frame_timestamps else None
        framerate_hz = (
                               frame_duration_ms ** -1) * 1000 if previous_frame_timestamps and frame_duration_ms > 0 else None

        return cls(
            recording_frame_number=recording_frame_number,
            connection_frame_number=connection_frame_number,
            from_recording_start_sec=ns_to_sec(frame_timestamps.timestamp_ns - recording_start_time_ns),
            perf_counter_ns=frame_timestamps.timestamp_ns,
            utc_sec=ns_to_sec(
                timebase.convert_perf_counter_ns_to_unix_ns(frame_timestamps.timestamp_ns, local_time=False)),
            local_iso8601=timebase.convert_perf_counter_ns_to_local_iso8601(frame_timestamps.timestamp_ns),

            frame_duration_ms=frame_duration_ms,
            framerate_hz=framerate_hz,

            initialized_ns=frame_timestamps.initialized_ns - recording_start_time_ns,
            pre_grab_ns=frame_timestamps.pre_frame_grab_ns - recording_start_time_ns,
            post_grab_ns=frame_timestamps.post_frame_grab_ns - recording_start_time_ns,
            pre_retrieve_ns=frame_timestamps.pre_frame_retrieve_ns - recording_start_time_ns,
            post_retrieve_ns=frame_timestamps.post_frame_retrieve_ns - recording_start_time_ns,
            pre_copy_to_camera_shm_ns=frame_timestamps.pre_copy_to_camera_shm_ns - recording_start_time_ns,
            post_copy_to_camera_shm_ns=frame_timestamps.post_copy_to_camera_shm_ns - recording_start_time_ns,
            pre_record_frame_ns=frame_timestamps.pre_frame_record_ns - recording_start_time_ns,
            post_record_frame_ns=frame_timestamps.post_frame_record_ns - recording_start_time_ns,

            during_frame_grab_ns=frame_timestamps.durations.during_frame_grab_ns,
            idle_before_retrieve_ns=frame_timestamps.durations.idle_before_retrieve_ns,
            during_frame_retrieve_ns=frame_timestamps.durations.during_frame_retrieve_ns,
            idle_before_frame_record_ns=frame_timestamps.durations.idle_before_frame_record_ns,
            during_frame_record_ns=frame_timestamps.durations.during_frame_record_ns,
            idle_before_copy_to_camera_shm_ns=frame_timestamps.durations.idle_before_copy_to_camera_shm_ns,
            during_copy_to_camera_shm_ns=frame_timestamps.durations.during_copy_to_camera_shm_ns,

            total_frame_processing_time_ns=frame_timestamps.durations.total_frame_processing_time_ns,
            total_camera_idle_time_ns=frame_timestamps.durations.total_camera_idle_time_ns,

        )
