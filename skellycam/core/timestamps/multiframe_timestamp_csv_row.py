from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from skellycam.core.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.time_unit_conversion import ns_to_ms

if TYPE_CHECKING:
    pass


class MultiframeTimestampsCSVRow(BaseModel):

    # Basic fields (similar to FrameTimestampCSVRow)
    multiframe_number: int

    # Timestamp fields
    from_recording_start_ms: float = Field(serialization_alias="timestamp.from_recording_start.ms")
    perf_counter_ns: float = Field(serialization_alias="timestamp.perf_counter_ns.ns")
    utc_sec: float = Field(serialization_alias="timestamp.utc.seconds")
    local_iso8601: str = Field(serialization_alias="timestamp.local.iso8601")

    # From-previous measures
    frame_duration_ms: float = Field(serialization_alias="from_previous.frame_duration.ms")
    framerate_hz: float = Field(serialization_alias="from_previous.framerate.hz")

    # Lifespan timestamp fields with statistical measures
    # initialized_ns
    initialized_ms_mean: float = Field(serialization_alias="frame.initialized.ms.mean")
    initialized_ms_median: float = Field(serialization_alias="frame.initialized.ms.median")
    initialized_ms_stddev: float = Field(serialization_alias="frame.initialized.ms.stddev")
    initialized_ms_range: float = Field(serialization_alias="frame.initialized.ms.range")
    
    # pre_grab_ns
    pre_grab_ms_mean: float = Field(serialization_alias="frame.pre_grab.ms.mean")
    pre_grab_ms_median: float = Field(serialization_alias="frame.pre_grab.ms.median")
    pre_grab_ms_stddev: float = Field(serialization_alias="frame.pre_grab.ms.stddev")
    pre_grab_ms_range: float = Field(serialization_alias="frame.pre_grab.ms.range")
    
    # post_grab_ns
    post_grab_ms_mean: float = Field(serialization_alias="frame.post_grab.ms.mean")
    post_grab_ms_median: float = Field(serialization_alias="frame.post_grab.ms.median")
    post_grab_ms_stddev: float = Field(serialization_alias="frame.post_grab.ms.stddev")
    post_grab_ms_range: float = Field(serialization_alias="frame.post_grab.ms.range")
    
    # pre_retrieve_ns
    pre_retrieve_ms_mean: float = Field(serialization_alias="frame.pre_retrieve.ms.mean")
    pre_retrieve_ms_median: float = Field(serialization_alias="frame.pre_retrieve.ms.median")
    pre_retrieve_ms_stddev: float = Field(serialization_alias="frame.pre_retrieve.ms.stddev")
    pre_retrieve_ms_range: float = Field(serialization_alias="frame.pre_retrieve.ms.range")
    
    # post_retrieve_ns
    post_retrieve_ms_mean: float = Field(serialization_alias="frame.post_retrieve.ms.mean")
    post_retrieve_ms_median: float = Field(serialization_alias="frame.post_retrieve.ms.median")
    post_retrieve_ms_stddev: float = Field(serialization_alias="frame.post_retrieve.ms.stddev")
    post_retrieve_ms_range: float = Field(serialization_alias="frame.post_retrieve.ms.range")
    
    # copy_to_camera_shm_ns
    copy_to_camera_shm_ms_mean: float = Field(serialization_alias="frame.copy_to_camera_shm.ms.mean")
    copy_to_camera_shm_ms_median: float = Field(serialization_alias="frame.copy_to_camera_shm.ms.median")
    copy_to_camera_shm_ms_stddev: float = Field(serialization_alias="frame.copy_to_camera_shm.ms.stddev")
    copy_to_camera_shm_ms_range: float = Field(serialization_alias="frame.copy_to_camera_shm.ms.range")
    
    # pre_retrieve_from_camera_shm_ns
    pre_retrieve_from_camera_shm_ms_mean: float = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.ms.mean")
    pre_retrieve_from_camera_shm_ms_median: float = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.ms.median")
    pre_retrieve_from_camera_shm_ms_stddev: float = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.ms.stddev")
    pre_retrieve_from_camera_shm_ms_range: float = Field(serialization_alias="frame.pre_retrieve_from_camera_shm.ms.range")
    
    # post_retrieve_from_camera_shm_ns
    post_retrieve_from_camera_shm_ms_mean: float = Field(serialization_alias="frame.post_retrieve_from_camera_shm.ms.mean")
    post_retrieve_from_camera_shm_ms_median: float = Field(serialization_alias="frame.post_retrieve_from_camera_shm.ms.median")
    post_retrieve_from_camera_shm_ms_stddev: float = Field(serialization_alias="frame.post_retrieve_from_camera_shm.ms.stddev")
    post_retrieve_from_camera_shm_ms_range: float = Field(serialization_alias="frame.post_retrieve_from_camera_shm.ms.range")
    
    # copy_to_multiframe_shm_ns
    pre_copy_to_multiframe_shm_ms_mean: float = Field(serialization_alias="frame.pre_copy_to_multiframe_shm.ms.mean")
    pre_copy_to_multiframe_shm_ms_median: float = Field(serialization_alias="frame.pre_copy_to_multiframe_shm.ms.median")
    pre_copy_to_multiframe_shm_ms_stddev: float = Field(serialization_alias="frame.pre_copy_to_multiframe_shm.ms.stddev")
    pre_copy_to_multiframe_shm_ms_range: float = Field(serialization_alias="frame.pre_copy_to_multiframe_shm.ms.range")
    
    # pre_retrieve_from_multiframe_shm_ns
    pre_retrieve_from_multiframe_shm_ms_mean: float = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.ms.mean")
    pre_retrieve_from_multiframe_shm_ms_median: float = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.ms.median")
    pre_retrieve_from_multiframe_shm_ms_stddev: float = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.ms.stddev")
    pre_retrieve_from_multiframe_shm_ms_range: float = Field(serialization_alias="frame.pre_retrieve_from_multiframe_shm.ms.range")
    
    # post_retrieve_from_multiframe_shm_ns
    post_retrieve_from_multiframe_shm_ms_mean: float = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.ms.mean")
    post_retrieve_from_multiframe_shm_ms_median: float = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.ms.median")
    post_retrieve_from_multiframe_shm_ms_stddev: float = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.ms.stddev")
    post_retrieve_from_multiframe_shm_ms_range: float = Field(serialization_alias="frame.post_retrieve_from_multiframe_shm.ms.range")
    
    # Lifespan duration fields with statistical measures
    # idle_before_grab_ns
    idle_before_grab_ms_mean: float = Field(serialization_alias="duration.idle_before_grab.ms.mean")
    idle_before_grab_ms_median: float = Field(serialization_alias="duration.idle_before_grab.ms.median")
    idle_before_grab_ms_stddev: float = Field(serialization_alias="duration.idle_before_grab.ms.stddev")
    idle_before_grab_ms_range: float = Field(serialization_alias="duration.idle_before_grab.ms.range")
    
    # during_frame_grab_ns
    during_frame_grab_ms_mean: float = Field(serialization_alias="duration.during_frame_grab.ms.mean")
    during_frame_grab_ms_median: float = Field(serialization_alias="duration.during_frame_grab.ms.median")
    during_frame_grab_ms_stddev: float = Field(serialization_alias="duration.during_frame_grab.ms.stddev")
    during_frame_grab_ms_range: float = Field(serialization_alias="duration.during_frame_grab.ms.range")
    
    # idle_before_retrieve_ns
    idle_before_retrieve_ms_mean: float = Field(serialization_alias="duration.idle_before_retrieve.ms.mean")
    idle_before_retrieve_ms_median: float = Field(serialization_alias="duration.idle_before_retrieve.ms.median")
    idle_before_retrieve_ms_stddev: float = Field(serialization_alias="duration.idle_before_retrieve.ms.stddev")
    idle_before_retrieve_ms_range: float = Field(serialization_alias="duration.idle_before_retrieve.ms.range")
    
    # during_frame_retrieve_ns
    during_frame_retrieve_ms_mean: float = Field(serialization_alias="duration.during_frame_retrieve.ms.mean")
    during_frame_retrieve_ms_median: float = Field(serialization_alias="duration.during_frame_retrieve.ms.median")
    during_frame_retrieve_ms_stddev: float = Field(serialization_alias="duration.during_frame_retrieve.ms.stddev")
    during_frame_retrieve_ms_range: float = Field(serialization_alias="duration.during_frame_retrieve.ms.range")
    
    # idle_before_copy_to_camera_shm_ns
    idle_before_copy_to_camera_shm_ms_mean: float = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.ms.mean")
    idle_before_copy_to_camera_shm_ms_median: float = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.ms.median")
    idle_before_copy_to_camera_shm_ms_stddev: float = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.ms.stddev")
    idle_before_copy_to_camera_shm_ms_range: float = Field(serialization_alias="duration.idle_before_copy_to_camera_shm.ms.range")
    
    # stored_in_camera_shm_ns
    stored_in_camera_shm_ms_mean: float = Field(serialization_alias="duration.stored_in_camera_shm.ms.mean")
    stored_in_camera_shm_ms_median: float = Field(serialization_alias="duration.stored_in_camera_shm.ms.median")
    stored_in_camera_shm_ms_stddev: float = Field(serialization_alias="duration.stored_in_camera_shm.ms.stddev")
    stored_in_camera_shm_ms_range: float = Field(serialization_alias="duration.stored_in_camera_shm.ms.range")
    
    # during_copy_from_camera_shm_ns
    during_copy_from_camera_shm_ms_mean: float = Field(serialization_alias="duration.during_copy_from_camera_shm.ms.mean")
    during_copy_from_camera_shm_ms_median: float = Field(serialization_alias="duration.during_copy_from_camera_shm.ms.median")
    during_copy_from_camera_shm_ms_stddev: float = Field(serialization_alias="duration.during_copy_from_camera_shm.ms.stddev")
    during_copy_from_camera_shm_ms_range: float = Field(serialization_alias="duration.during_copy_from_camera_shm.ms.range")
    
    # idle_before_copy_to_multiframe_shm_ns
    idle_before_copy_to_multiframe_shm_ms_mean: float = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.ms.mean")
    idle_before_copy_to_multiframe_shm_ms_median: float = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.ms.median")
    idle_before_copy_to_multiframe_shm_ms_stddev: float = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.ms.stddev")
    idle_before_copy_to_multiframe_shm_ms_range: float = Field(serialization_alias="duration.idle_before_copy_to_multiframe_shm.ms.range")
    
    # stored_in_multiframe_shm_ns
    stored_in_multiframe_shm_ms_mean: float = Field(serialization_alias="duration.stored_in_multiframe_shm.ms.mean")
    stored_in_multiframe_shm_ms_median: float = Field(serialization_alias="duration.stored_in_multiframe_shm.ms.median")
    stored_in_multiframe_shm_ms_stddev: float = Field(serialization_alias="duration.stored_in_multiframe_shm.ms.stddev")
    stored_in_multiframe_shm_ms_range: float = Field(serialization_alias="duration.stored_in_multiframe_shm.ms.range")
    
    # total_frame_acquisition_time_ns
    total_frame_acquisition_time_ms_mean: float = Field(serialization_alias="duration.total_frame_acquisition.ms.mean")
    total_frame_acquisition_time_ms_median: float = Field(serialization_alias="duration.total_frame_acquisition.ms.median")
    total_frame_acquisition_time_ms_stddev: float = Field(serialization_alias="duration.total_frame_acquisition.ms.stddev")
    total_frame_acquisition_time_ms_range: float = Field(serialization_alias="duration.total_frame_acquisition.ms.range")
    
    # total_ipc_travel_time_ns
    total_ipc_travel_time_ms_mean: float = Field(serialization_alias="duration.total_ipc_travel.ms.mean")
    total_ipc_travel_time_ms_median: float = Field(serialization_alias="duration.total_ipc_travel.ms.median")
    total_ipc_travel_time_ms_stddev: float = Field(serialization_alias="duration.total_ipc_travel.ms.stddev")
    total_ipc_travel_time_ms_range: float = Field(serialization_alias="duration.total_ipc_travel.ms.range")

    @classmethod
    def from_multiframe_timestamp(cls,
                                  mf_timestamps:MultiFrameTimestamps,
                                  timebase_mapping:TimebaseMapping,
                                  recording_started_time_ns:int,
                                  previous_mf_timestamps: MultiFrameTimestamps | None=None) -> "MultiframeTimestampsCSVRow":
        """
        Create a CSV row from a MultiframeTimestamps object.
        """
        frame_duration_ms = ns_to_ms(
            mf_timestamps.timestamp_ns - previous_mf_timestamps.timestamp_ns) if previous_mf_timestamps else None
        framerate_hz = (frame_duration_ms**-1)/1000 if previous_mf_timestamps and frame_duration_ms >0 else None
        return cls(
            multiframe_number=mf_timestamps.multiframe_number,
            from_recording_start_ms=ns_to_ms(mf_timestamps.timestamp_ns.median - recording_started_time_ns),
            perf_counter_ns=mf_timestamps.timestamp_ns.median,
            utc_sec=timebase_mapping.convert_perf_counter_ns_to_unix_ns(mf_timestamps.timestamp_ns.median, local_time=False),
            local_iso8601=timebase_mapping.convert_perf_counter_ns_to_local_iso8601(mf_timestamps.timestamp_ns.median),

            frame_duration_ms= frame_duration_ms,
            framerate_hz= framerate_hz,

            initialized_ms_mean=mf_timestamps.frame_initialized_ms.mean,
            initialized_ms_median=mf_timestamps.frame_initialized_ms.median,
            initialized_ms_stddev=mf_timestamps.frame_initialized_ms.standard_deviation,
            initialized_ms_range=mf_timestamps.frame_initialized_ms.range,

            pre_grab_ms_mean=mf_timestamps.pre_grab_ms.mean,
            pre_grab_ms_median=mf_timestamps.pre_grab_ms.median,
            pre_grab_ms_stddev=mf_timestamps.pre_grab_ms.standard_deviation,
            pre_grab_ms_range=mf_timestamps.pre_grab_ms.range,

            post_grab_ms_mean=mf_timestamps.post_grab_ms.mean,
            post_grab_ms_median=mf_timestamps.post_grab_ms.median,
            post_grab_ms_stddev=mf_timestamps.post_grab_ms.standard_deviation,
            post_grab_ms_range=mf_timestamps.post_grab_ms.range,

            pre_retrieve_ms_mean=mf_timestamps.pre_retrieve_ms.mean,
            pre_retrieve_ms_median=mf_timestamps.pre_retrieve_ms.median,
            pre_retrieve_ms_stddev=mf_timestamps.pre_retrieve_ms.standard_deviation,
            pre_retrieve_ms_range=mf_timestamps.pre_retrieve_ms.range,

            post_retrieve_ms_mean=mf_timestamps.post_retrieve_ms.mean,
            post_retrieve_ms_median=mf_timestamps.post_retrieve_ms.median,
            post_retrieve_ms_stddev=mf_timestamps.post_retrieve_ms.standard_deviation,
            post_retrieve_ms_range=mf_timestamps.post_retrieve_ms.range,

            copy_to_camera_shm_ms_mean=mf_timestamps.copy_to_camera_shm_ms.mean,
            copy_to_camera_shm_ms_median=mf_timestamps.copy_to_camera_shm_ms.median,
            copy_to_camera_shm_ms_stddev=mf_timestamps.copy_to_camera_shm_ms.standard_deviation,
            copy_to_camera_shm_ms_range=mf_timestamps.copy_to_camera_shm_ms.range,

            pre_retrieve_from_camera_shm_ms_mean=mf_timestamps.pre_retrieve_from_camera_shm_ms.mean,
            pre_retrieve_from_camera_shm_ms_median=mf_timestamps.pre_retrieve_from_camera_shm_ms.median,
            pre_retrieve_from_camera_shm_ms_stddev=mf_timestamps.pre_retrieve_from_camera_shm_ms.standard_deviation,
            pre_retrieve_from_camera_shm_ms_range=mf_timestamps.pre_retrieve_from_camera_shm_ms.range,

            post_retrieve_from_camera_shm_ms_mean=mf_timestamps.post_retrieve_from_camera_shm_ms.mean,
            post_retrieve_from_camera_shm_ms_median=mf_timestamps.post_retrieve_from_camera_shm_ms.median,
            post_retrieve_from_camera_shm_ms_stddev=mf_timestamps.post_retrieve_from_camera_shm_ms.standard_deviation,
            post_retrieve_from_camera_shm_ms_range=mf_timestamps.post_retrieve_from_camera_shm_ms.range,

            pre_copy_to_multiframe_shm_ms_mean=mf_timestamps.pre_copy_to_multiframe_shm_ms.mean,
            pre_copy_to_multiframe_shm_ms_median=mf_timestamps.pre_copy_to_multiframe_shm_ms.median,
            pre_copy_to_multiframe_shm_ms_stddev=mf_timestamps.pre_copy_to_multiframe_shm_ms.standard_deviation,
            pre_copy_to_multiframe_shm_ms_range=mf_timestamps.pre_copy_to_multiframe_shm_ms.range,

            pre_retrieve_from_multiframe_shm_ms_mean=mf_timestamps.pre_retrieve_from_multiframe_shm_ms.mean,
            pre_retrieve_from_multiframe_shm_ms_median=mf_timestamps.pre_retrieve_from_multiframe_shm_ms.median,
            pre_retrieve_from_multiframe_shm_ms_stddev=mf_timestamps.pre_retrieve_from_multiframe_shm_ms.standard_deviation,
            pre_retrieve_from_multiframe_shm_ms_range=mf_timestamps.pre_retrieve_from_multiframe_shm_ms.range,

            post_retrieve_from_multiframe_shm_ms_mean=mf_timestamps.post_retrieve_from_multiframe_shm_ms.mean,
            post_retrieve_from_multiframe_shm_ms_median=mf_timestamps.post_retrieve_from_multiframe_shm_ms.median,
            post_retrieve_from_multiframe_shm_ms_stddev=mf_timestamps.post_retrieve_from_multiframe_shm_ms.standard_deviation,
            post_retrieve_from_multiframe_shm_ms_range=mf_timestamps.post_retrieve_from_multiframe_shm_ms.range,

            idle_before_grab_ms_mean=mf_timestamps.idle_before_grab_ms.mean,
            idle_before_grab_ms_median=mf_timestamps.idle_before_grab_ms.median,
            idle_before_grab_ms_stddev=mf_timestamps.idle_before_grab_ms.standard_deviation,
            idle_before_grab_ms_range=mf_timestamps.idle_before_grab_ms.range,

            during_frame_grab_ms_mean=mf_timestamps.during_frame_grab_ms.mean,
            during_frame_grab_ms_median=mf_timestamps.during_frame_grab_ms.median,
            during_frame_grab_ms_stddev=mf_timestamps.during_frame_grab_ms.standard_deviation,
            during_frame_grab_ms_range=mf_timestamps.during_frame_grab_ms.range,

            idle_before_retrieve_ms_mean=mf_timestamps.idle_before_retrieve_ms.mean,
            idle_before_retrieve_ms_median=mf_timestamps.idle_before_retrieve_ms.median,
            idle_before_retrieve_ms_stddev=mf_timestamps.idle_before_retrieve_ms.standard_deviation,
            idle_before_retrieve_ms_range=mf_timestamps.idle_before_retrieve_ms.range,

            during_frame_retrieve_ms_mean=mf_timestamps.during_frame_retrieve_ms.mean,
            during_frame_retrieve_ms_median=mf_timestamps.during_frame_retrieve_ms.median,
            during_frame_retrieve_ms_stddev=mf_timestamps.during_frame_retrieve_ms.standard_deviation,
            during_frame_retrieve_ms_range=mf_timestamps.during_frame_retrieve_ms.range,

            idle_before_copy_to_camera_shm_ms_mean=mf_timestamps.idle_before_copy_to_camera_shm_ms.mean,
            idle_before_copy_to_camera_shm_ms_median=mf_timestamps.idle_before_copy_to_camera_shm_ms.median,
            idle_before_copy_to_camera_shm_ms_stddev=mf_timestamps.idle_before_copy_to_camera_shm_ms.standard_deviation,
            idle_before_copy_to_camera_shm_ms_range=mf_timestamps.idle_before_copy_to_camera_shm_ms.range,

            stored_in_camera_shm_ms_mean=mf_timestamps.stored_in_camera_shm_ms.mean,
            stored_in_camera_shm_ms_median=mf_timestamps.stored_in_camera_shm_ms.median,
            stored_in_camera_shm_ms_stddev=mf_timestamps.stored_in_camera_shm_ms.standard_deviation,
            stored_in_camera_shm_ms_range=mf_timestamps.stored_in_camera_shm_ms.range,

            during_copy_from_camera_shm_ms_mean=mf_timestamps.during_copy_from_camera_shm_ms.mean,
            during_copy_from_camera_shm_ms_median=mf_timestamps.during_copy_from_camera_shm_ms.median,
            during_copy_from_camera_shm_ms_stddev=mf_timestamps.during_copy_from_camera_shm_ms.standard_deviation,
            during_copy_from_camera_shm_ms_range=mf_timestamps.during_copy_from_camera_shm_ms.range,

            idle_before_copy_to_multiframe_shm_ms_mean=mf_timestamps.idle_before_copy_to_multiframe_shm_ms.mean,
            idle_before_copy_to_multiframe_shm_ms_median=mf_timestamps.idle_before_copy_to_multiframe_shm_ms.median,
            idle_before_copy_to_multiframe_shm_ms_stddev=mf_timestamps.idle_before_copy_to_multiframe_shm_ms.standard_deviation,
            idle_before_copy_to_multiframe_shm_ms_range=mf_timestamps.idle_before_copy_to_multiframe_shm_ms.range,

            stored_in_multiframe_shm_ms_mean=mf_timestamps.stored_in_multiframe_shm_ms.mean,
            stored_in_multiframe_shm_ms_median=mf_timestamps.stored_in_multiframe_shm_ms.median,
            stored_in_multiframe_shm_ms_stddev=mf_timestamps.stored_in_multiframe_shm_ms.standard_deviation,
            stored_in_multiframe_shm_ms_range=mf_timestamps.stored_in_multiframe_shm_ms.range,

            total_frame_acquisition_time_ms_mean=mf_timestamps.total_frame_acquisition_time_ms.mean,
            total_frame_acquisition_time_ms_median=mf_timestamps.total_frame_acquisition_time_ms.median,
            total_frame_acquisition_time_ms_stddev=mf_timestamps.total_frame_acquisition_time_ms.standard_deviation,
            total_frame_acquisition_time_ms_range=mf_timestamps.total_frame_acquisition_time_ms.range,

            total_ipc_travel_time_ms_mean=mf_timestamps.total_ipc_travel_time_ms.mean,
            total_ipc_travel_time_ms_median=mf_timestamps.total_ipc_travel_time_ms.median,
            total_ipc_travel_time_ms_stddev=mf_timestamps.total_ipc_travel_time_ms.standard_deviation,
            total_ipc_travel_time_ms_range=mf_timestamps.total_ipc_travel_time_ms.range,

        )

    def to_csv_row_dict(self) -> dict[str, float|int|str]:
        """
        Returns the values for the CSV row as a dictionary,
        with field names converted to a format suitable for CSV headers.
        """
        return self.model_dump(by_alias=True)