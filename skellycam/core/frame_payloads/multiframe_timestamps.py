from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.sample_statistics import DescriptiveStatistics

if TYPE_CHECKING:
    from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload


class MultiframeTimestamps(BaseModel):
    """
    Provides the mean, median, standard deviation, and range of the attributes of the frame lifecycle timestamps
    """

    frame_timestamps: dict[CameraIdString, FrameLifespanTimestamps] = Field(
        description="Timestamps for each camera's frame lifecycle on a given multi-frame payload")

    multiframe_number: int
    @classmethod
    def from_multiframe(cls, multiframe_payload: 'MultiFramePayload') -> 'MultiframeTimestamps':
        """
        Create a MultiframeLifespanTimestamps from a MultiFramePayload.
        """
        return cls(frame_timestamps={camera_id: frame.timestamps
                                     for camera_id, frame in multiframe_payload.frames.items()},
                   multiframe_number=multiframe_payload.multi_frame_number)


    @computed_field
    @property
    def timestamps_local_unix_ms(self) -> dict[CameraIdString, float]:
        return {camera_id: ts.timestamp_local_unix_ms for camera_id, ts in self.frame_timestamps.items()}


    @computed_field
    @property
    def timestamp_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.timestamp_local_unix_ms / 1e6 for ts in self.frame_timestamps.values()],
            name="timestamp_local_unix_ms",
            units="milliseconds")

    @computed_field
    @property
    def inter_camera_grab_range_ms(self) -> float:
        """
        Returns the range of the timestamps across all cameras in milliseconds.
        This is the difference between the maximum and minimum `timestamp_local_unix_ms` values from each camera, which
        are base on the midpoint between the pre-grab and post-grab timestamps.
        """
        return self.timestamp_local_unix_ms.range

    @computed_field
    @property
    def frame_initialized_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_initialized_local_unix_ms for ts in self.frame_timestamps.values()],
            name="frame_initialized_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def pre_grab_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.pre_grab_local_unix_ms for ts in self.frame_timestamps.values()],
            name="pre_grab_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def post_grab_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.post_grab_local_unix_ms for ts in self.frame_timestamps.values()],
            name="post_grab_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def pre_retrieve_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.pre_retrieve_local_unix_ms for ts in self.frame_timestamps.values()],
            name="pre_retrieve_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def post_retrieve_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.post_retrieve_local_unix_ms for ts in self.frame_timestamps.values()],
            name="post_retrieve_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def copy_to_camera_shm_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.copy_to_camera_shm_local_unix_ms for ts in self.frame_timestamps.values()],
            name="copy_to_camera_shm_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def retrieve_from_camera_shm_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.retrieve_from_camera_shm_local_unix_ms for ts in self.frame_timestamps.values()],
            name="retrieve_from_camera_shm_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def copy_to_multiframe_shm_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.copy_to_multiframe_shm_local_unix_ms for ts in self.frame_timestamps.values()],
            name="copy_to_multiframe_shm_local_unix_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def retrieve_from_multiframe_shm_local_unix_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.retrieve_from_multiframe_shm_local_unix_ms for ts in self.frame_timestamps.values()],
            name="retrieve_from_multiframe_shm_local_unix_ms",
            units="milliseconds"
        )


    @computed_field
    @property
    def idle_before_grab_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_grab_duration_ms for ts in self.frame_timestamps.values()],
            name="idle_before_grab_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def frame_grab_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_grab_duration_ms for ts in self.frame_timestamps.values()],
            name="frame_grab_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def idle_before_retrieve_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_retrieve_duration_ms for ts in self.frame_timestamps.values()],
            name="idle_before_retrieve_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def frame_retrieve_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_retrieve_duration_ms for ts in self.frame_timestamps.values()],
            name="frame_retrieve_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def idle_before_copy_to_camera_shm_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_camera_shm_duration_ms for ts in self.frame_timestamps.values()],
            name="idle_before_copy_to_camera_shm_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def idle_in_camera_shm_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_in_camera_shm_duration_ms for ts in self.frame_timestamps.values()],
            name="idle_in_camera_shm_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def idle_before_copy_to_multiframe_shm_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_multiframe_shm_duration_ms for ts in self.frame_timestamps.values()],
            name="idle_before_copy_to_multiframe_shm_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def idle_in_multiframe_shm_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_in_multiframe_shm_duration_ms for ts in self.frame_timestamps.values()],
            name="idle_in_multiframe_shm_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def total_frame_acquisition_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_frame_acquisition_duration_ms for ts in self.frame_timestamps.values()],
            name="total_frame_acquisition_duration_ms",
            units="milliseconds"
        )

    @computed_field
    @property
    def total_ipc_travel_duration_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_ipc_travel_duration_ms for ts in self.frame_timestamps.values()],
            name="total_ipc_travel_duration_ms",
            units="milliseconds"
        )
