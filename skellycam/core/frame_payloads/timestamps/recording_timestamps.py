from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from tabulate import tabulate

from skellycam.core.frame_payloads.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frame_payloads.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.sample_statistics import DescriptiveStatistics

import logging

from skellycam.utilities.time_unit_conversion import ns_to_ms

logger = logging.getLogger(__name__)


class RecordingTimestampsStats(BaseModel):
    """
    A class to hold statistics about timestamps in a recording session.
    This is used to generate statistics about the recording timestamps.
    """
    recording_name: str
    number_of_frames: int
    inter_camera_grab_range_ms: DescriptiveStatistics
    idle_before_grab_ms: DescriptiveStatistics
    during_frame_grab_ms: DescriptiveStatistics
    idle_before_retrieve_ms: DescriptiveStatistics
    during_frame_retrieve_ms: DescriptiveStatistics
    idle_before_copy_to_camera_shm_ms: DescriptiveStatistics
    stored_in_camera_shm_ms: DescriptiveStatistics
    idle_before_copy_to_multiframe_shm_ms: DescriptiveStatistics
    stored_in_multiframe_shm_ms: DescriptiveStatistics
    total_frame_acquisition_time_ms: DescriptiveStatistics
    total_ipc_travel_time_ms: DescriptiveStatistics

    @classmethod
    def from_recording_timestamps(cls, recording_timestamps):
        return cls(
            recording_name=recording_timestamps.recording_info.recording_name,
            number_of_frames=recording_timestamps.number_of_recorded_frames,
            inter_camera_grab_range_ms=recording_timestamps.inter_camera_grab_range_stats,
            idle_before_grab_ms=recording_timestamps.idle_before_grab_duration_stats,
            during_frame_grab_ms=recording_timestamps.during_frame_grab_stats,
            idle_before_retrieve_ms=recording_timestamps.idle_before_retrieve_duration_stats,
            during_frame_retrieve_ms=recording_timestamps.during_frame_retrieve_stats,
            idle_before_copy_to_camera_shm_ms=recording_timestamps.idle_before_copy_to_camera_shm_stats,
            stored_in_camera_shm_ms=recording_timestamps.stored_in_camera_shm_stats,
            idle_before_copy_to_multiframe_shm_ms=recording_timestamps.idle_before_copy_to_multiframe_shm_stats,
            stored_in_multiframe_shm_ms=recording_timestamps.stored_in_multiframe_shm_stats,
            total_frame_acquisition_time_ms=recording_timestamps.total_frame_acquisition_time_stats,
            total_ipc_travel_time_ms=recording_timestamps.total_ipc_travel_time_stats,
        )

    def __str__(self):
        """
        Create an attractive and informative string representation of the stats using tabulate,
        showing key statistics about recording timestamps and time spent in
        different stages of the frame acquisition process.
        """

        # Header with basic recording info
        header = f"Recording Statistics: {self.recording_name}\n"
        header += f"Total Frames: {self.number_of_frames}\n"
        header += "=" * 80 + "\n\n"

        # Frame timing section
        timing_section = "FRAME TIMING STATISTICS\n"
        timing_section += "-" * 80 + "\n"
        timing_section += f"Inter-camera grab range: {self.inter_camera_grab_range_ms}\n\n"

        # Frame acquisition pipeline section
        pipeline_section = "FRAME ACQUISITION PIPELINE\n"
        pipeline_section += "-" * 80 + "\n"

        # Create a list of all stages in order with their timing stats
        stages = [
            ("Idle before grab", self.idle_before_grab_ms),
            ("Frame grab", self.during_frame_grab_ms),
            ("Idle before retrieve", self.idle_before_retrieve_ms),
            ("Frame retrieve", self.during_frame_retrieve_ms),
            ("Idle before copy to camera SHM", self.idle_before_copy_to_camera_shm_ms),
            ("Stored in camera SHM", self.stored_in_camera_shm_ms),
            ("Idle before copy to multiframe SHM", self.idle_before_copy_to_multiframe_shm_ms),
            ("Stored in multiframe SHM", self.stored_in_multiframe_shm_ms),
        ]

        # Calculate total time for percentage calculations
        total_time = self.total_frame_acquisition_time_ms.mean + self.total_ipc_travel_time_ms.mean

        # Create table data for pipeline stages
        table_data = []
        for stage_name, stats in stages:
            percentage = (stats.mean / total_time) * 100 if total_time > 0 else 0
            table_data.append([
                stage_name,
                f"{stats.mean:.3f}",
                f"{stats.standard_deviation:.3f}",
                f"{stats.min:.3f}",
                f"{stats.max:.3f}",
                f"{percentage:.3f}%"
            ])

        # Create the pipeline table
        pipeline_table = tabulate(
            table_data,
            headers=["Stage", "Mean (ms)", "Std (ms)", "Min (ms)", "Max (ms)", "% of Total"],
            tablefmt="grid"
        )
        pipeline_section += pipeline_table + "\n\n"

        # Summary section with table
        summary_section = "SUMMARY METRICS\n"
        summary_section += "-" * 80 + "\n"

        summary_data = [
            ["Total frame acquisition time",
             f"{self.total_frame_acquisition_time_ms.mean:.3f}",
             f"{self.total_frame_acquisition_time_ms.standard_deviation:.3f}",
             f"{self.total_frame_acquisition_time_ms.min:.3f}",
             f"{self.total_frame_acquisition_time_ms.max:.3f}"],
            ["Total IPC travel time",
             f"{self.total_ipc_travel_time_ms.mean:.3f}",
             f"{self.total_ipc_travel_time_ms.standard_deviation:.3f}",
             f"{self.total_ipc_travel_time_ms.min:.3f}",
             f"{self.total_ipc_travel_time_ms.max:.3f}"]
        ]

        summary_table = tabulate(
            summary_data,
            headers=["Metric", "Mean (ms)", "Std (ms)", "Min (ms)", "Max (ms)"],
            tablefmt="grid"
        )
        summary_section += summary_table

        # Combine all sections
        return header + timing_section + pipeline_section + summary_section

class RecordingTimestamps(BaseModel):
    multiframe_timestamps: list[MultiFrameTimestamps] = Field(
        default_factory=list,
        description="List of timestamps for each multi-frame payload in the recording session")
    recording_start_ns: int | None = Field(
        default=None,
        description="The timestamp of the earliest 'grab' timestamp from the frames in the first multiframe of this recording, in nanoseconds. "
                    "This is as the Zero timebase to calculate relative timestamps for each multiframe payload.")
    recording_info: RecordingInfo


    def save_timestamps(self):
        """
        Saves the timestamps to a CSV file in the recording info's timestamps folder.
        The file is named with the recording name and has a .csv extension.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available to save")

        df = self.to_mf_dataframe()
        df.to_csv(f"{self.recording_info.timestamps_folder}/{self.recording_info.recording_name}_timestamps.csv",
                  index_label="multiframe_number")
        stats = self.to_stats()
        logger.info(f"Saved recording timestamps and stats to {self.recording_info.timestamps_folder} and {self.recording_info.camera_timestamps_folder}")
        logger.info(f"Recording stats:\n\n{stats}\n\n")
        Path(f"{self.recording_info.timestamps_folder}/{self.recording_info.recording_name}_stats.json").write_text(stats.model_dump_json(indent=2))
        dfs = self.to_camera_dataframes()
        for camera_id, camera_df in dfs.items():
            camera_df.to_csv(
                f"{self.recording_info.camera_timestamps_folder}/{self.recording_info.recording_name}_camera_{camera_id}_timestamps.csv",
                index_label="frame_number")
        logger.info(f"Saved recording timestamps and stats to {self.recording_info.timestamps_folder} and {self.recording_info.camera_timestamps_folder}")
        logger.info(f"Recording stats:\n\n{stats}\n\n")


    @property
    def number_of_recorded_frames(self) -> int:
        return len(self.multiframe_timestamps)

    def to_stats(self) -> RecordingTimestampsStats:
        """
        Converts the recording timestamps to a TimestampStats object.
        This is used to generate statistics about the recording timestamps.
        """
        return RecordingTimestampsStats.from_recording_timestamps(self)

    def add_multiframe(self, multiframe: MultiFramePayload):
        """
        Adds a multiframe payload to the recording timestamps.
        If the multiframe payload is empty, it will not be added.
        """
        if self.recording_start_ns is None:
            self.recording_start_ns = multiframe.earliest_timestamp_ns
        self.multiframe_timestamps.append(MultiFrameTimestamps.from_multiframe(multiframe=multiframe,
                                                                               recording_start_time_ns=self.recording_start_ns))

    @property
    def first_timestamp(self) -> MultiFrameTimestamps:
        """
        Returns the timestamp of the first multiframe payload in the recording session.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        return self.multiframe_timestamps[0]

    @property
    def recording_start_local_unix_ms(self) -> float:
        """Returns the timestamp of the first frame in the recording"""
        return min([mf_ts.frame_initialized_ms.mean for mf_ts in self.multiframe_timestamps])

    @property
    def timestamps_ms(self) -> list[float]:
        """
        Returns a list of timestamps in milliseconds for each multiframe payload,
        relative to the first frame.
        """
        return [ns_to_ms(mf.timestamp_ns.mean) - self.recording_start_local_unix_ms for mf in
                self.multiframe_timestamps]

    @property
    def frame_durations_ms(self) -> list[float]:
        """
        Returns the duration between consecutive frames in milliseconds.
        The first value is NaN since there's no previous frame.
        If there are no timestamps, returns an empty list.
        """
        if not self.timestamps_ms:
            return []
        return [np.nan] + list(np.diff(self.timestamps_ms))

    @property
    def frames_per_second(self) -> list[float]:
        return [duration ** -1 * 1e6 for duration in self.frame_durations_ms if duration > 0]

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
            samples=[ts.idle_before_grab_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_grab_ms",
            units="milliseconds"
        )

    @property
    def during_frame_grab_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame grab duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_frame_grab_ms.median for ts in self.multiframe_timestamps],
            name="frame_grab_duration_ms",
            units="milliseconds"
        )

    @property
    def idle_before_retrieve_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before retrieving a frame.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_retrieve_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_retrieve_ms",
            units="milliseconds"
        )

    @property
    def during_frame_retrieve_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame retrieve duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_frame_retrieve_ms.median for ts in self.multiframe_timestamps],
            name="during_frame_retrieve_ms",
            units="milliseconds"
        )

    @property
    def idle_before_copy_to_camera_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to camera shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_camera_shm_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_copy_to_camera_shm_ms",
            units="milliseconds"
        )

    @property
    def stored_in_camera_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time in camera shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.stored_in_camera_shm_ms.median for ts in self.multiframe_timestamps],
            name="stored_in_camera_shm_ms",
            units="milliseconds"
        )

    @property
    def during_copy_from_camera_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_copy_from_camera_shm_ms.median for ts in self.multiframe_timestamps],
            name="during_copy_from_camera_shm_ms",
            units="milliseconds"
        )

    @property
    def idle_before_copy_to_multiframe_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_multiframe_shm_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_copy_to_multiframe_shm_ms",
            units="milliseconds"
        )
    @property
    def stored_in_multiframe_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time in multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.stored_in_multiframe_shm_ms.median for ts in self.multiframe_timestamps],
            name="stored_in_multiframe_shm_ms",
            units="milliseconds"
        )

    @property
    def during_copy_from_multiframe_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_copy_from_multiframe_shm_ms.median for ts in self.multiframe_timestamps],
            name="during_copy_from_multiframe_shm_ms",
            units="milliseconds"
        )

    @property
    def total_frame_acquisition_time_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the total frame acquisition duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_frame_acquisition_time_ms.median for ts in self.multiframe_timestamps],
            name="total_frame_acquisition_time_ms",
            units="milliseconds"
        )

    @property
    def total_ipc_travel_time_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the total IPC travel duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_ipc_travel_time_ms.median for ts in self.multiframe_timestamps],
            name="total_ipc_travel_duration_ms",
            units="milliseconds"
        )

    def to_mf_dataframe(self) -> pd.DataFrame:
        records = [mf_ts.model_dump(exclude={'frame_timestamps', 'timestamps_local_unix_ms'}) for mf_ts in
                             self.multiframe_timestamps]

        return pd.DataFrame(records,
                            index=[mf_ts.multiframe_number for mf_ts in self.multiframe_timestamps])

    @property
    def timestamps_by_camera_id(self) -> dict[CameraIdString, list[FrameTimestamps]]:
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

    def to_camera_dataframes(self) -> dict[CameraIdString, pd.DataFrame]:
        """
        Returns a dictionary of dataframes for each camera in the recording.
        Each dataframe contains the timestamps for that camera.
        """
        camera_dfs = {}
        for camera_id, frame_timestamps in self.timestamps_by_camera_id.items():
            camera_dfs[camera_id] = pd.DataFrame([ts.model_dump() for ts in frame_timestamps],
                                                 index=self.frame_numbers)

        return camera_dfs
