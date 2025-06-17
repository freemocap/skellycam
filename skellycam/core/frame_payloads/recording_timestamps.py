import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frame_payloads.multiframe_timestamps import MultiframeTimestamps
from skellycam.utilities.sample_statistics import DescriptiveStatistics


class RecordingTimestamps(BaseModel):
    multiframe_timestamps: list[MultiframeTimestamps] = Field(
        default_factory=list,
        description="List of timestamps for each multi-frame payload in the recording session")

    def add_multiframe(self, multiframe:MultiFramePayload):
        """
        Adds a multiframe payload to the recording timestamps.
        If the multiframe payload is empty, it will not be added.
        """
        self.multiframe_timestamps.append(MultiframeTimestamps.from_multiframe(multiframe))

    @property
    def first_timestamp(self) -> MultiframeTimestamps:
        """
        Returns the timestamp of the first multiframe payload in the recording session.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        return self.multiframe_timestamps[0]

    @property
    def recording_start_ns(self) -> int:
        """Returns the timestamp of the first frame in the recording"""
        return self.first_timestamp.principal_camera_timestamps.timestamp_ns

    @property
    def timestamps_ns(self) -> list[int]:
        """
        Returns a list of timestamps in nanoseconds for each multiframe payload,
        relative to the first frame.
        """
        return [mf.principal_camera_timestamps.timestamp_ns - self.recording_start_ns
                for mf in self.multiframe_timestamps]

    @property
    def frame_durations_ns(self) -> list[float]:
        """
        Returns the duration between consecutive frames in nanoseconds.
        The first value is 0 since there's no previous frame.
        """
        return [0] + list(np.diff(self.timestamps_ns))

    @property
    def frames_per_second(self) -> list[float]:
        """
        Returns the instantaneous frames per second for each frame.
        """
        durations = self.frame_durations_ns
        # Avoid division by zero by replacing zeros with NaN
        durations_no_zero = np.array(durations, dtype=float)
        durations_no_zero[durations_no_zero == 0] = np.nan
        # Convert nanoseconds to seconds and calculate fps
        return list(1e9 / durations_no_zero)

    @property
    @computed_field
    def frame_initialized_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.frame_initialized_ns.mean for mf in self.multiframe_timestamps],
            name="frame_initialized_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def pre_grab_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.pre_grab_ns.mean for mf in self.multiframe_timestamps],
            name="pre_grab_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def post_grab_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.post_grab_ns.mean for mf in self.multiframe_timestamps],
            name="post_grab_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def pre_retrieve_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.pre_retrieve_ns.mean for mf in self.multiframe_timestamps],
            name="pre_retrieve_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def post_retrieve_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.post_retrieve_ns.mean for mf in self.multiframe_timestamps],
            name="post_retrieve_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def copy_to_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.copy_to_camera_shm_ns.mean for mf in self.multiframe_timestamps],
            name="copy_to_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def retrieve_from_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.retrieve_from_camera_shm_ns.mean for mf in self.multiframe_timestamps],
            name="retrieve_from_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def copy_to_multiframe_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.copy_to_multiframe_shm_ns.mean for mf in self.multiframe_timestamps],
            name="copy_to_multiframe_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def retrieve_from_multiframe_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.retrieve_from_multiframe_shm_ns.mean for mf in self.multiframe_timestamps],
            name="retrieve_from_multiframe_shm_ns",
            units="milliseconds"
        )

    @property
    @computed_field
    def timestamp_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.timestamp_ns.mean for mf in self.multiframe_timestamps],
            name="timestamp_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_grab_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.idle_before_grab_ns.mean for mf in self.multiframe_timestamps],
            name="idle_before_grab_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def frame_grab_duration_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.frame_grab_duration_ns.mean for mf in self.multiframe_timestamps],
            name="frame_grab_duration_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_retrieve_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.idle_before_retrieve_ns.mean for mf in self.multiframe_timestamps],
            name="idle_before_retrieve_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def frame_retrieve_duration_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.frame_retrieve_duration_ns.mean for mf in self.multiframe_timestamps],
            name="frame_retrieve_duration_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_copy_to_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.idle_before_copy_to_camera_shm_ns.mean for mf in self.multiframe_timestamps],
            name="idle_before_copy_to_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def time_in_camera_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.time_in_camera_shm_ns.mean for mf in self.multiframe_timestamps],
            name="time_in_camera_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def idle_before_copy_to_multiframe_shm_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.idle_before_copy_to_multiframe_shm_ns.mean for mf in self.multiframe_timestamps],
            name="idle_before_copy_to_multiframe_shm_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def time_in_multiframe_shm(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.time_in_multiframe_shm.mean for mf in self.multiframe_timestamps],
            name="time_in_multiframe_shm",
            units="milliseconds"
        )
    @property
    @computed_field
    def total_frame_acquisition_time_ns(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.total_frame_acquisition_time_ns.mean for mf in self.multiframe_timestamps],
            name="total_frame_acquisition_time_ns",
            units="milliseconds"
        )
    @property
    @computed_field
    def total_ipc_travel_time(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.total_ipc_travel_time.mean for mf in self.multiframe_timestamps],
            name="total_ipc_travel_time",
            units="milliseconds"
        )
    @property
    @computed_field
    def inter_camera_timestamp_stats(self) -> DescriptiveStatistics:
        return DescriptiveStatistics.from_samples(
            samples=[mf.inter_camera_timestamp_stats_ms.mean for mf in self.multiframe_timestamps],
            name="inter_camera_timestamp_stats",
            units="milliseconds"
        )
    @property
    @computed_field
    def frame_duration_stats(self) -> DescriptiveStatistics:
        """Statistics about frame durations across the recording"""
        return DescriptiveStatistics.from_samples(
            samples=[duration / 1_000_000 for duration in self.frame_durations_ns[1:]],  # Skip the first 0
            name="frame_duration",
            units="milliseconds"
        )
    @property
    @computed_field
    def fps_stats(self) -> DescriptiveStatistics:
        """Statistics about frames per second across the recording"""
        # Filter out any NaN or infinite values
        valid_fps = [fps for fps in self.frames_per_second if np.isfinite(fps)]
        return DescriptiveStatistics.from_samples(
            samples=valid_fps,
            name="frames_per_second",
            units="fps"
        )