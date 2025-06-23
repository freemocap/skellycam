from pydantic import BaseModel, Field

from typing import TYPE_CHECKING

from skellycam.core.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.time_unit_conversion import ns_to_ms, ns_to_sec

if TYPE_CHECKING:
    from skellycam.core.frame_payloads.frame_metadata import FrameMetadata


class FrameTimestampsCSVRow(BaseModel):
    recording_frame_number: int
    connection_frame_number: int

    # Timestamp fields
    from_recording_start_sec: float = Field(serialization_alias="timestamp.from_recording_start.sec")
    utc_sec: float = Field(serialization_alias="timestamp.utc.seconds")
    local_iso8601: str = Field(serialization_alias="timestamp.local.iso8601")
    perf_counter_ns: int = Field(serialization_alias="timestamp.perf_counter_ns.ns")

    # From-previous measures (i.e. frame duration and framerate, which require knowledge of the previous frame)
    frame_duration_ms: float|None = Field(serialization_alias="from_previous.frame_duration.ms")
    framerate_hz: float|None = Field(serialization_alias="from_previous.framerate.hz")

    # Lifespan timestamp fields
    initialized_ns: int = Field(serialization_alias="frame.initialized.ns")
    pre_grab_ns: int = Field(serialization_alias="frame.pre_grab.ns")
    post_grab_ns: int = Field(serialization_alias="frame.post_grab.ns")
    pre_retrieve_ns: int = Field(serialization_alias="frame.pre_retrieve.ns")
    post_retrieve_ns: int = Field(serialization_alias="frame.post_retrieve.ns")
    copy_to_camera_shm_ns: int = Field(serialization_alias="frame.copy_to_camera_shm.ns")
    pre_retrieve_from_camera_shm_ns: int = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.ns")
    post_retrieve_from_camera_shm_ns: int = Field(serialization_alias="frame.post_retrieve_from_camera_shm.ns")
    copy_to_multiframe_shm_ns: int = Field(serialization_alias="frame.copy_to_multiframe_shm.ns")
    pre_retrieve_from_multiframe_shm_ns: int = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.ns")
    post_retrieve_from_multiframe_shm_ns: int = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.ns")

    # Lifespan duration fields
    idle_before_grab_ns: int = Field(serialization_alias="duration.idle_before_grab.ns")
    during_frame_grab_ns: int = Field(serialization_alias="duration.during_frame_grab.ns")
    idle_before_retrieve_ns: int = Field(serialization_alias="duration.idle_before_retrieve.ns")
    during_frame_retrieve_ns: int = Field(serialization_alias="duration.during_frame_retrieve.ns")
    idle_before_copy_to_camera_shm_ns: int = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.ns")
    stored_in_camera_shm_ns: int = Field(serialization_alias="duration.stored_in_camera_shm.ns")
    during_copy_from_camera_shm_ns: int = Field(serialization_alias="duration.during_copy_from_camera_shm.ns")
    idle_before_copy_to_multiframe_shm_ns: int = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.ns")
    stored_in_multiframe_shm_ns: int = Field(serialization_alias="duration.stored_in_multiframe_shm.ns")
    total_frame_acquisition_time_ns: int = Field(serialization_alias="duration.total_frame_acquisition.ns")
    total_ipc_travel_time_ns: int = Field(serialization_alias="duration.total_ipc_travel.ns")

    @classmethod
    def from_frame_timestamps(cls,
                              frame_timestamps: FrameTimestamps,
                              recording_frame_number: int,
                              connection_frame_number: int,
                              recording_start_time_ns: int,
                              previous_frame_timestamps: FrameTimestamps| None = None,
                              ) -> "FrameTimestampsCSVRow":

        timebase: TimebaseMapping = frame_timestamps.timebase_mapping

        frame_duration_ms = ns_to_ms(
            frame_timestamps.timestamp_ns - previous_frame_timestamps.timestamp_ns) if previous_frame_timestamps else None
        framerate_hz = (frame_duration_ms**-1)*1000 if previous_frame_timestamps and frame_duration_ms >0 else None

        return cls(
            recording_frame_number=recording_frame_number,
            connection_frame_number=connection_frame_number,
            from_recording_start_sec=ns_to_sec(frame_timestamps.timestamp_ns - recording_start_time_ns),
            perf_counter_ns=frame_timestamps.timestamp_ns,
            utc_sec=ns_to_sec(timebase.convert_perf_counter_ns_to_unix_ns(frame_timestamps.timestamp_ns, local_time=False)),
            local_iso8601=timebase.convert_perf_counter_ns_to_local_iso8601(frame_timestamps.timestamp_ns),

            frame_duration_ms=frame_duration_ms,
            framerate_hz= framerate_hz,

            initialized_ns=frame_timestamps.frame_initialized_ns-recording_start_time_ns,
            pre_grab_ns=frame_timestamps.pre_frame_grab_ns-recording_start_time_ns,
            post_grab_ns=frame_timestamps.post_frame_grab_ns-recording_start_time_ns,
            pre_retrieve_ns=frame_timestamps.pre_frame_retrieve_ns-recording_start_time_ns,
            post_retrieve_ns=frame_timestamps.post_frame_retrieve_ns-recording_start_time_ns,
            copy_to_camera_shm_ns=frame_timestamps.pre_copy_to_camera_shm_ns-recording_start_time_ns,
            pre_retrieve_from_camera_shm_ns=frame_timestamps.pre_retrieve_from_camera_shm_ns-recording_start_time_ns,
            post_retrieve_from_camera_shm_ns=frame_timestamps.post_retrieve_from_camera_shm_ns-recording_start_time_ns,
            copy_to_multiframe_shm_ns=frame_timestamps.pre_copy_to_multiframe_shm_ns-recording_start_time_ns,
            pre_retrieve_from_multiframe_shm_ns=frame_timestamps.pre_retrieve_from_multiframe_shm_ns-recording_start_time_ns,
            post_retrieve_from_multiframe_shm_ns=frame_timestamps.post_retrieve_from_multiframe_shm_ns-recording_start_time_ns,

            idle_before_grab_ns=frame_timestamps.durations.idle_before_grab_ns,
            during_frame_grab_ns=frame_timestamps.durations.during_frame_grab_ns,
            idle_before_retrieve_ns=frame_timestamps.durations.idle_before_retrieve_ns,
            during_frame_retrieve_ns=frame_timestamps.durations.during_frame_retrieve_ns,
            idle_before_copy_to_camera_shm_ns=frame_timestamps.durations.idle_before_copy_to_camera_shm_ns,
            stored_in_camera_shm_ns=frame_timestamps.durations.stored_in_camera_shm_ns,
            during_copy_from_camera_shm_ns=frame_timestamps.durations.during_copy_from_camera_shm_ns,
            idle_before_copy_to_multiframe_shm_ns=frame_timestamps.durations.idle_before_copy_to_multiframe_shm_ns,
            stored_in_multiframe_shm_ns=frame_timestamps.durations.stored_in_multiframe_shm_ns,
            total_frame_acquisition_time_ns=frame_timestamps.durations.total_frame_acquisition_time_ns,
            total_ipc_travel_time_ns=frame_timestamps.durations.total_ipc_travel_time_ns,
        )

