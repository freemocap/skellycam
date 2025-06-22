from functools import cached_property
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from skellycam.core.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics
from skellycam.utilities.time_unit_conversion import ns_to_ms

if TYPE_CHECKING:
    from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload


class MultiFrameTimestamps(BaseModel):
    """
    Provides the statstistics for the timestamps of a multi-frame payload.
    """

    frame_timestamps: dict[CameraIdString, FrameTimestamps] = Field(
        description="Timestamps for each camera's frame lifecycle on a given multi-frame payload")

    multiframe_number: int

    recording_start_time_ns: int

    @classmethod
    def from_multiframe(cls, multiframe: 'MultiFramePayload', recording_start_time_ns:int) -> 'MultiFrameTimestamps':
        """
        Create a MultiframeLifespanTimestamps from a MultiFramePayload.
        """
        return cls(frame_timestamps={camera_id: frame.frame_metadata.timestamps
                                     for camera_id, frame in multiframe.frames.items()},
                     recording_start_time_ns=recording_start_time_ns,
                   multiframe_number=multiframe.multi_frame_number)

    @cached_property
    def timestamps_ns(self) -> dict[CameraIdString, int]:
        return {camera_id: ts.timestamp_ns for camera_id, ts in self.frame_timestamps.items()}

    @cached_property
    def timestamp_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts_ns for ts_ns in self.timestamps_ns.values()],
            name="timestamp_ns",
            units="nanoseconds")

    @cached_property
    def inter_camera_grab_range_ms(self) -> float:
        """
        Returns the range of the timestamps across all cameras in milliseconds.
        This is the difference between the maximum and minimum `timestamp_ns` values from each camera, which
        are base on the midpoint between the pre-grab and post-grab timestamps and converted to milliseconds.
        """
        return ns_to_ms(self.timestamp_ns.range)

    @cached_property
    def frame_initialized_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.frame_initialized_ns) for ts in self.frame_timestamps.values()],
            name="frame_initialized_ms",
            units="milliseconds"
        )

    @cached_property
    def pre_grab_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_frame_grab_ns) for ts in self.frame_timestamps.values()],
            name="pre_grab_ms",
            units="milliseconds"
        )

    @cached_property
    def post_grab_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.post_frame_grab_ns) for ts in self.frame_timestamps.values()],
            name="post_grab_ms",
            units="milliseconds"
        )

    @cached_property
    def pre_retrieve_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_frame_retrieve_ns) for ts in self.frame_timestamps.values()],
            name="pre_retrieve_ms",
            units="milliseconds"
        )

    @cached_property
    def post_retrieve_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.post_frame_retrieve_ns) for ts in self.frame_timestamps.values()],
            name="post_retrieve_ms",
            units="milliseconds"
        )

    @cached_property
    def copy_to_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_copy_to_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="copy_to_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def pre_retrieve_from_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_retrieve_from_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="retrieve_from_camera_shm_ms",
            units="milliseconds"
        )
    @cached_property
    def post_retrieve_from_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.post_retrieve_from_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="post_retrieve_from_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def pre_copy_to_multiframe_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_copy_to_multiframe_shm_ns) for ts in self.frame_timestamps.values()],
            name="pre_copy_to_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def pre_retrieve_from_multiframe_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_retrieve_from_multiframe_shm_ns) for ts in self.frame_timestamps.values()],
            name="pre_retrieve_from_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def post_retrieve_from_multiframe_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.post_retrieve_from_multiframe_shm_ns) for ts in self.frame_timestamps.values()],
            name="post_retrieve_from_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_grab_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.idle_before_grab_ns) for ts in self.frame_timestamps.values()],
            name="idle_before_grab_ms",
            units="milliseconds"
        )

    @cached_property
    def during_frame_grab_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.during_frame_grab_ns) for ts in self.frame_timestamps.values()],
            name="during_frame_grab_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_retrieve_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.idle_before_retrieve_ns) for ts in self.frame_timestamps.values()],
            name="idle_before_retrieve_ms",
            units="milliseconds"
        )

    @cached_property
    def during_frame_retrieve_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.during_frame_retrieve_ns) for ts in self.frame_timestamps.values()],
            name="during_frame_retrieve_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_copy_to_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.idle_before_copy_to_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="idle_before_copy_to_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def stored_in_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.stored_in_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="stored_in_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def during_copy_from_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.during_copy_from_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="during_copy_from_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_copy_to_multiframe_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.idle_before_copy_to_multiframe_shm_ns) for ts in self.frame_timestamps.values()],
            name="idle_before_copy_to_multiframe_shm_ms",
            units="milliseconds"
        )
    @cached_property
    def stored_in_multiframe_shm_ms(self) -> DescriptiveStatistics:
        """
        Time spent in the multi-frame shared memory buffer.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.stored_in_multiframe_shm_ns) for ts in self.frame_timestamps.values()],
            name="stored_in_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def during_copy_from_multiframe_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.during_copy_from_multiframe_shm_ns) for ts in self.frame_timestamps.values()],
            name="during_copy_from_multiframe_shm_ms",
            units="milliseconds"
        )


    @cached_property
    def total_frame_acquisition_time_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.total_frame_acquisition_time_ns) for ts in self.frame_timestamps.values()],
            name="total_frame_acquisition_time_ms",
            units="milliseconds"
        )

    @cached_property
    def total_ipc_travel_time_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.total_ipc_travel_time_ns) for ts in self.frame_timestamps.values()],
            name="total_ipc_travel_time_ms",
            units="milliseconds"
        )

    @cached_property
    def total_camera_to_recorder_time_ms(self) -> DescriptiveStatistics:
        """
        Returns the combined statistics for total camera-to-recorder time (acquisition + IPC).
        This is an approximation based on the sum of means, min, max and a combined standard deviation.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.total_camera_to_recorder_time_ns) for ts in self.frame_timestamps.values()],
            name="total_camera_to_recorder_time_ns",
            units="milliseconds"
        )

