import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frame_payloads.multiframe_timestamps import MultiframeTimestamps
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.sample_statistics import DescriptiveStatistics


class RecordingTimestamps(BaseModel):
    multiframe_timestamps: list[MultiframeTimestamps] = Field(
        default_factory=list,
        description="List of timestamps for each multi-frame payload in the recording session")

    @property
    def number_of_recorded_frames(self) -> int:
        return len(self.multiframe_timestamps)

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
    def recording_start_local_unix_ms(self) -> float:
        """Returns the timestamp of the first frame in the recording"""
        return min([mf_ts.frame_initialized_local_unix_ms.mean for mf_ts in self.multiframe_timestamps])


    @property
    def timestamps_local_unix_ms(self) -> list[float]:
        """
        Returns a list of timestamps in nanoseconds for each multiframe payload,
        relative to the first frame.
        """
        return [mf.timestamp_local_unix_ms.mean - self.recording_start_local_unix_ms for mf in self.multiframe_timestamps]

    @property
    def frame_durations_ms(self) -> list[float]:
        """
        Returns the duration between consecutive frames in milliseconds.
        The first value is NaN since there's no previous frame.
        If there are no timestamps, returns an empty list.
        """
        if not self.timestamps_local_unix_ms:
            return []
        return [np.nan] + list(np.diff(self.timestamps_local_unix_ms))

    @property
    def frames_per_second(self) -> list[float]:
        return [duration** -1 * 1e6 for duration in self.frame_durations_ms if duration > 0 ]


    @property
    def fps_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frames per second.
        """
        return DescriptiveStatistics.from_samples(
            samples=self.frames_per_second,
            name="frames_per_second",
            units="Hz"
        )

    @property
    def frame_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame durations in milliseconds.
        """
        return DescriptiveStatistics.from_samples(
            samples=self.frame_durations_ms,
            name="frame_durations_ms",
            units="milliseconds"
        )
    @property
    def inter_camera_grab_range_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the inter-camera grab range in nanoseconds.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.inter_camera_grab_range_ms for ts in self.multiframe_timestamps],
            name="inter_camera_grab_range_ms",
            units="milliseconds"
        )


    @property
    def idle_before_grab_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before grabbing a frame.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_grab_duration_ms for ts in self.multiframe_timestamps],
            name="idle_before_grab_duration_ms",
            units="milliseconds"
        )

    @property
    def frame_grab_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame grab duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_grab_duration_ms for ts in self.multiframe_timestamps],
            name="frame_grab_duration_ms",
            units="milliseconds"
        )
    @property
    def idle_before_retrieve_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before retrieving a frame.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_retrieve_duration_ms for ts in self.multiframe_timestamps],
            name="idle_before_retrieve_duration_ms",
            units="milliseconds"
        )

    @property
    def frame_retrieve_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame retrieve duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.frame_retrieve_duration_ms for ts in self.multiframe_timestamps],
            name="frame_retrieve_duration_ms",
            units="milliseconds"
        )

    @property
    def idle_before_copy_to_camera_shm_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to camera shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_camera_shm_duration_ms for ts in self.multiframe_timestamps],
            name="idle_before_copy_to_camera_shm_duration_ms",
            units="milliseconds"
        )

    @property
    def idle_in_camera_shm_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time in camera shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_in_camera_shm_duration_ms for ts in self.multiframe_timestamps],
            name="idle_in_camera_shm_duration_ms",
            units="milliseconds"
        )
    @property
    def idle_before_copy_to_multiframe_shm_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_multiframe_shm_duration_ms for ts in self.multiframe_timestamps],
            name="idle_before_copy_to_multiframe_shm_duration_ms",
            units="milliseconds"
        )
    @property
    def idle_in_multiframe_shm_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time in multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_in_multiframe_shm_duration_ms for ts in self.multiframe_timestamps],
            name="idle_in_multiframe_shm_duration_ms",
            units="milliseconds"
        )


    @property
    def total_frame_acquisition_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the total frame acquisition duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_frame_acquisition_duration_ms for ts in self.multiframe_timestamps],
            name="total_frame_acquisition_duration_ms",
            units="milliseconds"
        )
    @property
    def total_ipc_travel_duration_stats (self) -> DescriptiveStatistics:
        """
        Returns the statistics of the total IPC travel duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_ipc_travel_duration_ms for ts in self.multiframe_timestamps],
            name="total_ipc_travel_duration_ms",
            units="milliseconds"
        )

    def to_mf_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([mf_ts.model_dump(exclude={'frame_timestamps', 'principal_camera_id'}) for mf_ts in self.multiframe_timestamps],
                          index=[mf_ts.multiframe_number for mf_ts in self.multiframe_timestamps])

    @property
    def timestamps_by_camera_id(self) -> dict[CameraIdString, list[FrameLifespanTimestamps]]:
        """
        Returns a dictionary mapping camera IDs to lists of FrameLifespanTimestamps.
        Each list contains the timestamps for that camera across all multiframe payloads.
        """
        camera_timestamps = {}
        for mf_ts in self.multiframe_timestamps:
            for camera_id, frame_ts in mf_ts.frame_timestamps.items():
                if camera_id not in camera_timestamps:
                    camera_timestamps[camera_id] = []
                camera_timestamps[camera_id].append(frame_ts)
        return camera_timestamps
    @property
    def frame_numbers(self) -> list[int]:
        """
        Returns a list of frame numbers for all frames in the recording.
        This is derived from the multiframe timestamps.
        """
        return [mf_ts.multiframe_number for mf_ts in self.multiframe_timestamps]

    def to_camera_dataframe(self) -> dict[CameraIdString, pd.DataFrame]:
        """
        Returns a dictionary of dataframes for each camera in the recording.
        Each dataframe contains the timestamps for that camera.
        """
        camera_dfs = {}
        for camera_id, frame_timestamps in self.timestamps_by_camera_id.items():
            camera_dfs[camera_id] = pd.DataFrame([ts.model_dump() for ts in frame_timestamps],
                                                 index=self.frame_numbers)

        return camera_dfs