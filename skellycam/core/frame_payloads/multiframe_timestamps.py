from typing import Any

from pydantic import BaseModel, Field, computed_field

from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.sample_statistics import DescriptiveStatistics

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload


class MultiframeTimestamps(BaseModel):
    """
    Provides the mean, median, standard deviation, and range of the attributes of the frame lifecycle timestamps
    """

    frame_timestamps: dict[CameraIdString, FrameLifespanTimestamps] = Field(
        description="Timestamps for each camera's frame lifecycle on a given multi-frame payload")
    principal_camera_id: CameraIdString = Field(description="The id of the principal camera, which will be used "
                                                            "as the zero-reference for this multi-frame payload")

    @classmethod
    def from_multiframe(cls, multiframe_payload: 'MultiFramePayload') -> 'MultiframeTimestamps':
        """
        Create a MultiframeLifespanTimestamps from a MultiFramePayload.
        """
        return cls(frame_timestamps={camera_id: frame.timestamps
                                     for camera_id, frame in multiframe_payload.frames.items()},
                   principal_camera_id=multiframe_payload.principal_camera_id)

    @property
    def principal_camera_timestamps(self) -> FrameLifespanTimestamps:
        return self.frame_timestamps[self.principal_camera_id]

    @property
    def multiframe_start_time_ns(self) -> int:
        return self.principal_camera_timestamps.frame_initialized_ns

    @property
    def timestamps_perf_counter_ns(self) -> list[int]:
        return [ts.timestamp_ns for ts in self.frame_timestamps.values()]

    @property
    def inter_camera_timestamps_ns(self) -> list[int]:
        return [ts.timestamp_ns - self.principal_camera_timestamps.timestamp_ns for ts in
                self.frame_timestamps.values()]

    @property
    def inter_camera_timestamp_stats_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts / 1_000_000 for ts in self.inter_camera_timestamps_ns],
            name="inter_camera_timestamp_range_ns",
            units="milliseconds"
        )

    @property# Direct properties for each attribute in FrameLifespanTimestamps
    @computed_field
    def frame_initialized_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_initialized_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="frame_initialized_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def pre_grab_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.pre_grab_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="pre_grab_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def post_grab_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.post_grab_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="post_grab_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def pre_retrieve_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.pre_retrieve_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="pre_retrieve_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def post_retrieve_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.post_retrieve_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="post_retrieve_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def copy_to_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.copy_to_camera_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="copy_to_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def retrieve_from_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.retrieve_from_camera_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="retrieve_from_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def copy_to_multiframe_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.copy_to_multiframe_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="copy_to_multiframe_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def retrieve_from_multiframe_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.retrieve_from_multiframe_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="retrieve_from_multiframe_shm_ns",
            units="milliseconds"
        )

    @property
    @computed_field
    def timestamp_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.timestamp_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="timestamp_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_grab_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_grab_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="idle_before_grab_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def frame_grab_duration_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_grab_duration_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="frame_grab_duration_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_retrieve_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_retrieve_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="idle_before_retrieve_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def frame_retrieve_duration_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_retrieve_duration_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="frame_retrieve_duration_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_copy_to_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_camera_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="idle_before_copy_to_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def time_in_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.time_in_camera_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="time_in_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_copy_to_multiframe_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_multiframe_shm_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="idle_before_copy_to_multiframe_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def time_in_multiframe_shm(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.time_in_multiframe_shm / 1_000_000 for ts in self.frame_timestamps.values()],
            name="time_in_multiframe_shm",
            units="milliseconds"
        )
    @property
    @computed_field
    def total_frame_acquisition_time_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_frame_acquisition_time_ns / 1_000_000 for ts in self.frame_timestamps.values()],
            name="total_frame_acquisition_time_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def total_ipc_travel_time(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_ipc_travel_time / 1_000_000 for ts in self.frame_timestamps.values()],
            name="total_ipc_travel_time",
            units="milliseconds"
        )