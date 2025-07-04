from pydantic import BaseModel, Field

from skellycam.core.camera_group.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.time_unit_conversion import ns_to_ms, ns_to_sec


class MultiFrameTimestampsCSVRow(BaseModel):
    recording_frame_number: int # number of frames since the recording started
    connection_frame_number: int # number of frames since the camera group connected

    # Timestamp fields
    from_recording_start_sec: float = Field(serialization_alias="timestamp.from_recording_start.sec")
    utc_sec: float = Field(serialization_alias="timestamp.utc.seconds")
    local_iso8601: str = Field(serialization_alias="timestamp.local.iso8601")
    perf_counter_ns: float = Field(serialization_alias="timestamp.perf_counter_ns.ns")

    inter_camera_grab_range_ms: float = Field(serialization_alias="multiframe.inter_camera_grab_range.ms",
        description="The range of time in milliseconds between the first and last camera grab in a multi-camera frame."
    )
    # From-previous measures (i.e. frame duration and framerate, which require knowledge of the previous frame)
    frame_duration_ms: float|None = Field(serialization_alias="from_previous.frame_duration.ms")
    framerate_hz: float|None = Field(serialization_alias="from_previous.framerate.hz")

    # Lifespan timestamp fields
    initialized_mean_ms: float = Field(serialization_alias="frame.initialized.mean.ms")
    initialized_std_ms: float = Field(serialization_alias="frame.initialized.std.ms")
    pre_grab_mean_ms: float = Field(serialization_alias="frame.pre_grab.mean.ms")
    pre_grab_std_ms: float = Field(serialization_alias="frame.pre_grab.std.ms")
    post_grab_mean_ms: float = Field(serialization_alias="frame.post_grab.mean.ms")
    post_grab_std_ms: float = Field(serialization_alias="frame.post_grab.std.ms")
    pre_retrieve_mean_ms: float = Field(serialization_alias="frame.pre_retrieve.mean.ms")
    pre_retrieve_std_ms: float = Field(serialization_alias="frame.pre_retrieve.std.ms")
    post_retrieve_mean_ms: float = Field(serialization_alias="frame.post_retrieve.mean.ms")
    post_retrieve_std_ms: float = Field(serialization_alias="frame.post_retrieve.std.ms")
    pre_copy_to_camera_shm_mean_ms: float = Field(serialization_alias="frame.copy_to_camera_shm.mean.ms")
    pre_copy_to_camera_shm_std_ms: float = Field(serialization_alias="frame.copy_to_camera_shm.std.ms")
    pre_retrieve_from_camera_shm_mean_ms: float = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.mean.ms")
    pre_retrieve_from_camera_shm_std_ms: float = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.std.ms")
    post_retrieve_from_camera_shm_mean_ms: float = Field(serialization_alias="frame.post_retrieve_from_camera_shm.mean.ms")
    post_retrieve_from_camera_shm_std_ms: float = Field(serialization_alias="frame.post_retrieve_from_camera_shm.std.ms")
    pre_copy_to_multiframe_shm_mean_ms: float = Field(serialization_alias="frame.copy_to_multiframe_shm.mean.ms")
    pre_copy_to_multiframe_shm_std_ms: float = Field(serialization_alias="frame.copy_to_multiframe_shm.std.ms")
    pre_retrieve_from_multiframe_shm_mean_ms: float = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.mean.ms")
    pre_retrieve_from_multiframe_shm_std_ms: float = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.std.ms")
    post_retrieve_from_multiframe_shm_mean_ms: float = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.mean.ms")
    post_retrieve_from_multiframe_shm_std_ms: float = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.std.ms")

    # Lifespan duration fields
    idle_before_grab_mean_ms: float = Field(serialization_alias="duration.idle_before_grab.mean.ms")
    idle_before_grab_std_ms: float = Field(serialization_alias="duration.idle_before_grab.std.ms")
    during_frame_grab_mean_ms: float = Field(serialization_alias="duration.during_frame_grab.mean.ms")
    during_frame_grab_std_ms: float = Field(serialization_alias="duration.during_frame_grab.std.ms")
    idle_before_retrieve_mean_ms: float = Field(serialization_alias="duration.idle_before_retrieve.mean.ms")
    idle_before_retrieve_std_ms: float = Field(serialization_alias="duration.idle_before_retrieve.std.ms")
    during_frame_retrieve_mean_ms: float = Field(serialization_alias="duration.during_frame_retrieve.mean.ms")
    during_frame_retrieve_std_ms: float = Field(serialization_alias="duration.during_frame_retrieve.std.ms")
    idle_before_copy_to_camera_shm_mean_ms: float = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.mean.ms")
    idle_before_copy_to_camera_shm_std_ms: float = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.std.ms")
    stored_in_camera_shm_mean_ms: float = Field(serialization_alias="duration.stored_in_camera_shm.mean.ms")
    stored_in_camera_shm_std_ms: float = Field(serialization_alias="duration.stored_in_camera_shm.std.ms")
    during_copy_from_camera_shm_mean_ms: float = Field(serialization_alias="duration.during_copy_from_camera_shm.mean.ms")
    during_copy_from_camera_shm_std_ms: float = Field(serialization_alias="duration.during_copy_from_camera_shm.std.ms")
    idle_before_copy_to_multiframe_shm_mean_ms: float = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.mean.ms")
    idle_before_copy_to_multiframe_shm_std_ms: float = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.std.ms")
    stored_in_multiframe_shm_mean_ms: float = Field(serialization_alias="duration.stored_in_multiframe_shm.mean.ms")
    stored_in_multiframe_shm_std_ms: float = Field(serialization_alias="duration.stored_in_multiframe_shm.std.ms")
    total_frame_acquisition_time_mean_ms: float = Field(serialization_alias="duration.total_frame_acquisition.mean.ms")
    total_frame_acquisition_time_std_ms: float = Field(serialization_alias="duration.total_frame_acquisition.std.ms")
    total_ipc_travel_time_mean_ms: float = Field(serialization_alias="duration.total_ipc_travel.mean.ms")
    total_ipc_travel_time_std_ms: float = Field(serialization_alias="duration.total_ipc_travel.std.ms")

    @classmethod
    def from_mf_timestamps(cls,
                           mf_timestamps: MultiFrameTimestamps,
                           recording_frame_number: int,
                           connection_frame_number: int,
                           recording_start_time_ns: int,
                           previous_mf_timestamps: MultiFrameTimestamps| None = None,
                           ) -> "MultiFrameTimestampsCSVRow":

        timebase: TimebaseMapping = mf_timestamps.timebase_mapping
        frame_duration_ms = None
        framerate_hz = None
        if previous_mf_timestamps:
            frame_duration_ms = ns_to_ms(mf_timestamps.timestamp_ns.mean - previous_mf_timestamps.timestamp_ns.mean)
        if frame_duration_ms is not None and frame_duration_ms > 0:
            framerate_hz = (frame_duration_ms**-1)*1000

        recording_start_ms = ns_to_ms(recording_start_time_ns)
        return cls(
            recording_frame_number=recording_frame_number,
            connection_frame_number=connection_frame_number,
            from_recording_start_sec=ns_to_sec(mf_timestamps.timestamp_ns.mean - recording_start_time_ns),
            perf_counter_ns=mf_timestamps.timestamp_ns.mean,
            utc_sec=ns_to_sec(timebase.convert_perf_counter_ns_to_unix_ns(mf_timestamps.timestamp_ns.mean, local_time=False)),
            local_iso8601=timebase.convert_perf_counter_ns_to_local_iso8601(mf_timestamps.timestamp_ns.mean),
            inter_camera_grab_range_ms =mf_timestamps.inter_camera_grab_range_ms,
            frame_duration_ms=frame_duration_ms,
            framerate_hz= framerate_hz,
            initialized_mean_ms=mf_timestamps.frame_initialized_ms.mean - recording_start_ms,
            pre_grab_mean_ms=mf_timestamps.pre_grab_ms.mean - recording_start_ms,
            post_grab_mean_ms=mf_timestamps.post_grab_ms.mean - recording_start_ms,
            pre_retrieve_mean_ms=mf_timestamps.pre_retrieve_ms.mean - recording_start_ms,
            post_retrieve_mean_ms=mf_timestamps.post_retrieve_ms.mean - recording_start_ms,
            pre_copy_to_camera_shm_mean_ms=mf_timestamps.pre_copy_to_camera_shm_ms.mean - recording_start_ms,
            pre_retrieve_from_camera_shm_mean_ms=mf_timestamps.pre_retrieve_from_camera_shm_ms.mean - recording_start_ms,
            post_retrieve_from_camera_shm_mean_ms=mf_timestamps.post_retrieve_from_camera_shm_ms.mean - recording_start_ms,
            pre_copy_to_multiframe_shm_mean_ms=mf_timestamps.pre_copy_to_multiframe_shm_ms.mean - recording_start_ms,
            pre_retrieve_from_multiframe_shm_mean_ms=mf_timestamps.pre_retrieve_from_multiframe_shm_ms.mean - recording_start_ms,
            post_retrieve_from_multiframe_shm_mean_ms=mf_timestamps.post_retrieve_from_multiframe_shm_ms.mean - recording_start_ms,

            idle_before_grab_mean_ms=mf_timestamps.idle_before_grab_ms.mean,
            during_frame_grab_mean_ms=mf_timestamps.during_frame_grab_ms.mean,
            idle_before_retrieve_mean_ms=mf_timestamps.idle_before_retrieve_ms.mean,
            during_frame_retrieve_mean_ms=mf_timestamps.during_frame_retrieve_ms.mean,
            idle_before_copy_to_camera_shm_mean_ms=mf_timestamps.idle_before_copy_to_camera_shm_ms.mean,
            stored_in_camera_shm_mean_ms=mf_timestamps.stored_in_camera_shm_ms.mean,
            during_copy_from_camera_shm_mean_ms=mf_timestamps.during_copy_from_camera_shm_ms.mean,
            idle_before_copy_to_multiframe_shm_mean_ms=mf_timestamps.idle_before_copy_to_multiframe_shm_ms.mean,
            stored_in_multiframe_shm_mean_ms=mf_timestamps.stored_in_multiframe_shm_ms.mean,
            total_frame_acquisition_time_mean_ms=mf_timestamps.total_frame_acquisition_time_ms.mean,
            total_ipc_travel_time_mean_ms=mf_timestamps.total_ipc_travel_time_ms.mean,

            initialized_std_ms=mf_timestamps.frame_initialized_ms.standard_deviation,
            pre_grab_std_ms=mf_timestamps.pre_grab_ms.standard_deviation,
            post_grab_std_ms=mf_timestamps.post_grab_ms.standard_deviation,
            pre_retrieve_std_ms=mf_timestamps.pre_retrieve_ms.standard_deviation,
            post_retrieve_std_ms=mf_timestamps.post_retrieve_ms.standard_deviation,
            pre_copy_to_camera_shm_std_ms=mf_timestamps.pre_copy_to_camera_shm_ms.standard_deviation,
            pre_retrieve_from_camera_shm_std_ms=mf_timestamps.pre_retrieve_from_camera_shm_ms.standard_deviation,
            post_retrieve_from_camera_shm_std_ms=mf_timestamps.post_retrieve_from_camera_shm_ms.standard_deviation,
            pre_copy_to_multiframe_shm_std_ms=mf_timestamps.pre_copy_to_multiframe_shm_ms.standard_deviation,
            pre_retrieve_from_multiframe_shm_std_ms=mf_timestamps.pre_retrieve_from_multiframe_shm_ms.standard_deviation,
            post_retrieve_from_multiframe_shm_std_ms=mf_timestamps.post_retrieve_from_multiframe_shm_ms.standard_deviation,

            idle_before_grab_std_ms=mf_timestamps.idle_before_grab_ms.standard_deviation,
            during_frame_grab_std_ms=mf_timestamps.during_frame_grab_ms.standard_deviation,
            idle_before_retrieve_std_ms=mf_timestamps.idle_before_retrieve_ms.standard_deviation,
            during_frame_retrieve_std_ms=mf_timestamps.during_frame_retrieve_ms.standard_deviation,
            idle_before_copy_to_camera_shm_std_ms=mf_timestamps.idle_before_copy_to_camera_shm_ms.standard_deviation,
            stored_in_camera_shm_std_ms=mf_timestamps.stored_in_camera_shm_ms.standard_deviation,
            during_copy_from_camera_shm_std_ms=mf_timestamps.during_copy_from_camera_shm_ms.standard_deviation,
            idle_before_copy_to_multiframe_shm_std_ms=mf_timestamps.idle_before_copy_to_multiframe_shm_ms.standard_deviation,
            stored_in_multiframe_shm_std_ms=mf_timestamps.stored_in_multiframe_shm_ms.standard_deviation,
            total_frame_acquisition_time_std_ms=mf_timestamps.total_frame_acquisition_time_ms.standard_deviation,
            total_ipc_travel_time_std_ms=mf_timestamps.total_ipc_travel_time_ms.standard_deviation,
        )





