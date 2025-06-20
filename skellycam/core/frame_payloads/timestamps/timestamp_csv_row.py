from pydantic import BaseModel, Field

from typing import TYPE_CHECKING

from skellycam.core.frame_payloads.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.time_unit_conversion import ns_to_ms, ns_to_sec

if TYPE_CHECKING:
    from skellycam.core.frame_payloads.frame_metadata import FrameMetadata


class FrameTimestampsCSVRow(BaseModel):
    frame_number: int

    # Timestamp fields
    from_recording_start_ms: float = Field(serialization_alias="timestamp.from_recording_start.ms")
    perf_counter_ns: int = Field(serialization_alias="timestamp.perf_counter_ns.ns")
    utc_sec: float = Field(serialization_alias="timestamp.utc.seconds")
    local_iso8601: str = Field(serialization_alias="timestamp.local.iso8601")

    # From-previous measures (i.e. frame duration and framerate, which require knowledge of the previous frame)
    frame_duration_ms: float = Field(serialization_alias="from_previous.frame_duration.ms")
    framerate_hz: float = Field(serialization_alias="from_previous.framerate.hz")

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
    def from_frame_metadata(cls,
                            frame_metadata: 'FrameMetadata',
                            recording_start_time_ns: int,
                            previous_frame_timestamps: FrameTimestamps| None = None,
                            ) -> "FrameTimestampsCSVRow":
        timestamps = frame_metadata.timestamps
        timebase: TimebaseMapping = timestamps.timebase_mapping

        frame_duration_ms = ns_to_ms(
            timestamps.timestamp_ns - previous_frame_timestamps.timestamp_ns) if previous_frame_timestamps else None
        framerate_hz = (frame_duration_ms**-1)/1000 if previous_frame_timestamps and frame_duration_ms >0 else None

        return cls(
            frame_number=frame_metadata.frame_number,
            from_recording_start_ms=ns_to_ms(timestamps.timestamp_ns - recording_start_time_ns),
            perf_counter_ns=timestamps.timestamp_ns,
            utc_sec=ns_to_sec(timebase.convert_perf_counter_ns_to_unix_ns(timestamps.timestamp_ns, local_time=False)),
            local_iso8601=timebase.convert_perf_counter_ns_to_local_iso8601(timestamps.timestamp_ns),

            frame_duration_ms=frame_duration_ms,
            framerate_hz= framerate_hz,

            initialized_ns=timestamps.frame_initialized_ns,
            pre_grab_ns=timestamps.pre_frame_grab_ns,
            post_grab_ns=timestamps.post_frame_grab_ns,
            pre_retrieve_ns=timestamps.pre_frame_retrieve_ns,
            post_retrieve_ns=timestamps.post_frame_retrieve_ns,
            copy_to_camera_shm_ns=timestamps.pre_copy_to_camera_shm_ns,
            pre_retrieve_from_camera_shm_ns=timestamps.pre_retrieve_from_camera_shm_ns,
            post_retrieve_from_camera_shm_ns=timestamps.post_retrieve_from_camera_shm_ns,
            copy_to_multiframe_shm_ns=timestamps.pre_copy_to_multiframe_shm_ns,
            pre_retrieve_from_multiframe_shm_ns=timestamps.pre_retrieve_from_multiframe_shm_ns,
            post_retrieve_from_multiframe_shm_ns=timestamps.post_retrieve_from_multiframe_shm_ns,

            idle_before_grab_ns=timestamps.durations["idle_before_grab_ns"],
            during_frame_grab_ns=timestamps.durations["during_frame_grab_ns"],
            idle_before_retrieve_ns=timestamps.durations["idle_before_retrieve_ns"],
            during_frame_retrieve_ns=timestamps.durations["during_frame_retrieve_ns"],
            idle_before_copy_to_camera_shm_ns=timestamps.durations["idle_before_copy_to_camera_shm_ns"],
            stored_in_camera_shm_ns=timestamps.durations["stored_in_camera_shm_ns"],
            during_copy_from_camera_shm_ns=timestamps.durations["during_copy_from_camera_shm_ns"],
            idle_before_copy_to_multiframe_shm_ns=timestamps.durations["idle_before_copy_to_multiframe_shm_ns"],
            stored_in_multiframe_shm_ns=timestamps.durations["stored_in_multiframe_shm_ns"],
            total_frame_acquisition_time_ns=timestamps.durations["total_frame_acquisition_time_ns"],
            total_ipc_travel_time_ns=timestamps.durations["total_ipc_travel_time_ns"],
        )

    def to_csv_row_dict(self) -> dict[str, float|int|str]:
        """
        Returns the values for the CSV row as a dictionary,
        with field names converted to a format suitable for CSV headers.
        """
        return self.model_dump(by_alias=True)