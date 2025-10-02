import logging
from dataclasses import dataclass
from functools import cached_property

from skellycam.core.frame_payloads.frame_metadata import FrameMetadata

from skellycam.core.camera_group.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics
from skellycam.utilities.time_unit_conversion import ns_to_ms

logger = logging.getLogger(__name__)

@dataclass
class MultiFrameTimestamps:
    """
    Provides the statstistics for the timestamps of a multi-frame payload.
    """

    frame_timestamps: dict[CameraIdString, FrameTimestamps]
    multiframe_number: int

    recording_start_time_ns: int

    @classmethod
    def from_frame_metadata(cls,
                            frame_metadata_by_camera: dict[CameraIdString,FrameMetadata],
                            recording_start_time_ns: int) -> 'MultiFrameTimestamps':
        """
        Create a MultiFrameTimestamps from a dictionary of FrameTimestamps.
        """
        frame_numbers = {camera_id: frame_metadata.frame_number for camera_id, frame_metadata in frame_metadata_by_camera.items()}

        if len(set(frame_numbers.values())) > 1:
            raise ValueError(f"All cameras must have the same frame number for a multi-frame payload, received:  frame_numbers={frame_numbers}")

        frame_timestamps = {camera_id: frame_metadata.timestamps for camera_id, frame_metadata in
                            frame_metadata_by_camera.items()}

        return cls(frame_timestamps=frame_timestamps,
                   multiframe_number=set(frame_numbers.values()).pop(),
                   recording_start_time_ns=recording_start_time_ns)

    @cached_property
    def timebase_mapping(self) -> TimebaseMapping:
        """
        Returns the timebase mapping for the multi-frame timestamps.
        This is derived from the timestamps of the first camera in the frame_timestamps.
        """
        if not self.frame_timestamps:
            raise ValueError("No frame timestamps available to derive timebase mapping.")
        tbs = [f.timebase_mapping for f in self.frame_timestamps.values()]
        if not all(tb == tbs[0] for tb in tbs):
            raise ValueError("All frame timestamps must have the same timebase mapping.")
        return tbs[0]

    @cached_property
    def timestamp_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ts_ns for ts_ns in self.timestamps_ns.values()],
            name="timestamp_ns",
            units="nanoseconds")

    @cached_property
    def timestamps_ns(self) -> dict[CameraIdString, int]:
        return {camera_id: ts.timestamp_ns for camera_id, ts in self.frame_timestamps.items()}

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
            samples=[ns_to_ms(ts.initialized_ns) for ts in self.frame_timestamps.values()],
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
    def pre_frame_record_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_frame_record_ns) for ts in self.frame_timestamps.values()],
            name="record_frame_ms",
            units="milliseconds"
        )

    @cached_property
    def post_frame_record_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.post_frame_record_ns) for ts in self.frame_timestamps.values()],
            name="post_frame_record_ms",
            units="milliseconds"
        )

    @cached_property
    def pre_put_in_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.pre_copy_to_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="pre_put_in_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def post_put_in_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.post_copy_to_camera_shm_ns) for ts in self.frame_timestamps.values()],
            name="post_put_in_camera_shm_ms",
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
    def during_copy_to_camera_shm_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.during_copy_to_camera_shm_ns) for ts in
                     self.frame_timestamps.values()],
            name="during_copy_to_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_frame_record_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.idle_before_frame_record_ns) for ts in self.frame_timestamps.values()],
            name="idle_before_record_ms",
            units="milliseconds"
        )

    @cached_property
    def during_frame_record_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.during_frame_record_ns) for ts in self.frame_timestamps.values()],
            name="during_frame_record_ns",
            units="milliseconds"
        )


    @cached_property
    def total_frame_processing_time_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.total_frame_processing_time_ns) for ts in self.frame_timestamps.values()],
            name="total_frame_processing_time_ms",
            units="milliseconds"
        )
    @cached_property
    def total_camera_idle_time_ms(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[ns_to_ms(ts.durations.total_camera_idle_time_ns) for ts in self.frame_timestamps.values()],
            name="total_idle_time_ms",
            units="milliseconds"
        )