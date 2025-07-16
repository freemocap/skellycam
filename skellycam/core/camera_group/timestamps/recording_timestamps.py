import logging
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict

from skellycam.core.camera_group.timestamps.frame_timestamp_csv_row import FrameTimestampsCSVRow
from skellycam.core.camera_group.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.camera_group.timestamps.multiframe_csv_row import MultiFrameTimestampsCSVRow
from skellycam.core.camera_group.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics
from skellycam.utilities.time_unit_conversion import ns_to_ms, ms_to_sec, ns_to_sec

logger = logging.getLogger(__name__)

def find_earliest_frame_metadata(frame_metadatas: dict[CameraIdString, FrameMetadata]) -> int:

    if len(frame_metadatas) == 0:
        raise ValueError("The multiframe record array is empty.")
    ts = []
    for metadata in frame_metadatas.values():
        ts.append(metadata.timestamps.timestamp_ns)
    if len(ts) == 0:
        raise ValueError("No metadata found in the multiframe record array.")
    return int(np.min(ts))

class RecordingTimestamps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    multiframe_timestamps: list[MultiFrameTimestamps] = Field(
        description="List of timestamps for each multi-frame payload in the recording session")
    recording_start_time_ns: int= Field(
        description="The start time of the recording session in nanoseconds. "
                    "This is used to calculate relative timestamps for each multiframe payload."
    )

    recording_info: RecordingInfo


    @classmethod
    def from_frame_metadata_by_camera(cls,
                                      recording_info: RecordingInfo,
                                      frame_metadatas_by_camera: dict[CameraIdString, list[FrameMetadata]]):
        recording_start_time_ns = find_earliest_frame_metadata({camera_id: frame_metadata[0] for camera_id, frame_metadata in frame_metadatas_by_camera.items()})
        frame_counts = [len(frame_metadata) for frame_metadata in frame_metadatas_by_camera.values()]

        if len(set(frame_counts)) > 1:
            raise ValueError("All cameras must have the same number of frames recorded. "
                             f"Found {len(frame_metadatas_by_camera)} cameras with different frame counts: "
                             f"{[len(frame_metadata) for frame_metadata in frame_metadatas_by_camera.values()]}")
        frame_count = frame_counts[0]
        frame_metadata_by_multiframe:list[dict[CameraIdString, FrameMetadata]] = []
        for frame_number in range(frame_count):
            frame_metadata = {}
            for camera_id, frame_metadata_list in frame_metadatas_by_camera.items():
                if frame_number >= len(frame_metadata_list):
                    raise ValueError(f"Camera {camera_id} does not have enough frames recorded. "
                                     f"Expected {frame_count}, but got {len(frame_metadata_list)}.")
                frame_metadata[camera_id] = frame_metadata_list[frame_number]
            frame_metadata_by_multiframe.append(frame_metadata)



        multiframe_timestamps = [MultiFrameTimestamps.from_frame_metadata(frame_metadata_by_camera=frame_metadata_by_camera,
                                                                          recording_start_time_ns=recording_start_time_ns)
                                 for frame_metadata_by_camera in frame_metadata_by_multiframe]

        previous_frame_number = multiframe_timestamps[0].multiframe_number-1
        previous_timestamp = None
        for mf_ts in multiframe_timestamps:
            if not mf_ts.multiframe_number == previous_frame_number + 1:
                raise ValueError(f"Multiframe numbers are not sequential. Expected {previous_frame_number + 1}, "
                                 f"but got {mf_ts.multiframe_number}.")
            if previous_timestamp is not None and mf_ts.timestamp_ns.mean < previous_timestamp:
                raise ValueError(f"Timestamps are not monotonically increasing. Previous: {previous_timestamp}, "
                                 f"Current: {mf_ts.timestamp_ns.mean}")
            previous_frame_number = mf_ts.multiframe_number
            previous_timestamp = mf_ts.timestamp_ns.mean

        return cls(
            multiframe_timestamps=multiframe_timestamps,
            recording_start_time_ns=recording_start_time_ns,
            recording_info=recording_info
        )


    @cached_property
    def number_of_recorded_frames(self) -> int:
        return len(self.multiframe_timestamps)

    @cached_property
    def number_of_cameras(self) -> int:
        return len(self.multiframe_timestamps[0].frame_timestamps.values())

    @cached_property
    def total_duration_sec(self) -> float:
        """
        Returns the total duration of the recording in seconds.
        This is calculated as the difference between the last and first multiframe timestamps.
        If there are no multiframe timestamps, returns 0.0.
        """
        if not self.multiframe_timestamps:
            return 0.0
        return ns_to_sec(
            self.multiframe_timestamps[-1].timestamp_ns.mean - self.multiframe_timestamps[0].timestamp_ns.mean)

    @cached_property
    def first_timestamp(self) -> MultiFrameTimestamps:
        """
        Returns the timestamp of the first multiframe payload in the recording session.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        return self.multiframe_timestamps[0]

    @cached_property
    def timestamps_ms(self) -> list[float]:
        """
        Returns a list of timestamps in milliseconds for each multiframe payload,
        relative to the first frame.
        """
        if self.recording_start_time_ns is None:
            raise ValueError("Recording start time is not set. Cannot calculate timestamps.")
        if not self.multiframe_timestamps:
            return []
        return [ns_to_ms(mf.timestamp_ns.mean - self.recording_start_time_ns) for mf in
                self.multiframe_timestamps]

    @cached_property
    def frame_durations_ms(self) -> list[float]:
        """
        Returns the duration between consecutive frames in milliseconds.
        The first value is NaN since there's no previous frame.
        If there are no timestamps, returns an empty list.
        """
        if not self.timestamps_ms:
            return []
        return [np.nan] + list(np.diff(self.timestamps_ms))

    @cached_property
    def frames_per_second(self) -> list[float]:
        return [ms_to_sec(duration) ** -1 for duration in self.frame_durations_ms if duration > 0]

    @cached_property
    def framerate_stats(self) -> DescriptiveStatistics:

        if len(self.frames_per_second) == 0:
            # Handle the case where we can't calculate framerate (only one frame)
            raise ValueError("Cannot calculate framerate statistics with fewer than 2 frames")

        return DescriptiveStatistics.from_samples(
            samples=self.frames_per_second,
            name="frames_per_second",
            units="Hz"
        )

    @cached_property
    def frame_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame durations in milliseconds.
        """
        return DescriptiveStatistics.from_samples(
            samples=self.frame_durations_ms,
            name="frame_durations_ms",
            units="milliseconds"
        )

    @cached_property
    def inter_camera_grab_range_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the inter-camera grab range in nanoseconds.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.inter_camera_grab_range_ms for ts in self.multiframe_timestamps],
            name="inter_camera_grab_range_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_grab_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before grabbing a frame.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_grab_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_grab_ms",
            units="milliseconds"
        )

    @cached_property
    def during_frame_grab_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame grab duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_frame_grab_ms.median for ts in self.multiframe_timestamps],
            name="frame_grab_duration_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_retrieve_duration_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before retrieving a frame.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_retrieve_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_retrieve_ms",
            units="milliseconds"
        )

    @cached_property
    def during_frame_retrieve_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the frame retrieve duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_frame_retrieve_ms.median for ts in self.multiframe_timestamps],
            name="during_frame_retrieve_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_copy_to_camera_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to camera shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_camera_shm_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_copy_to_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def stored_in_camera_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time in camera shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.stored_in_camera_shm_ms.median for ts in self.multiframe_timestamps],
            name="stored_in_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def during_copy_from_camera_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_copy_from_camera_shm_ms.median for ts in self.multiframe_timestamps],
            name="during_copy_from_camera_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def idle_before_copy_to_multiframe_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.idle_before_copy_to_multiframe_shm_ms.median for ts in self.multiframe_timestamps],
            name="idle_before_copy_to_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def stored_in_multiframe_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time in multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.stored_in_multiframe_shm_ms.median for ts in self.multiframe_timestamps],
            name="stored_in_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def during_copy_from_multiframe_shm_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the idle time before copying to multiframe shared memory.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.during_copy_from_multiframe_shm_ms.median for ts in self.multiframe_timestamps],
            name="during_copy_from_multiframe_shm_ms",
            units="milliseconds"
        )

    @cached_property
    def total_frame_acquisition_time_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the total frame acquisition duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_frame_acquisition_time_ms.median for ts in self.multiframe_timestamps],
            name="total_frame_acquisition_time_ms",
            units="milliseconds"
        )

    @cached_property
    def total_ipc_travel_time_stats(self) -> DescriptiveStatistics:
        """
        Returns the statistics of the total IPC travel duration.
        """
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_ipc_travel_time_ms.median for ts in self.multiframe_timestamps],
            name="total_ipc_travel_duration_ms",
            units="milliseconds"
        )

    @cached_property
    def total_camera_to_recorder_time_stats(self) -> DescriptiveStatistics:
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        return DescriptiveStatistics.from_samples(
            samples=[ts.total_camera_to_recorder_time_ms.median for ts in self.multiframe_timestamps],
            name="total_camera_to_recorder_time_ms",
            units="milliseconds"
        )

    @cached_property
    def timestamps_by_camera_id(self) -> dict[CameraIdString, list[FrameTimestamps]]:
        """
        Returns a dictionary mapping camera IDs to lists of FrameLifespanTimestamps.
        Each list contains the timestamps for that camera across all multiframe payloads.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        camera_timestamps = {}
        for mf_ts in self.multiframe_timestamps:
            for camera_id, frame_ts in mf_ts.frame_timestamps.items():
                if camera_id not in camera_timestamps:
                    camera_timestamps[camera_id] = []
                camera_timestamps[camera_id].append(frame_ts)
        return camera_timestamps

    @cached_property
    def frame_numbers(self) -> list[int]:
        """
        Returns a list of frame numbers for all frames in the recording.
        This is derived from the multiframe timestamps.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        return [mf_ts.multiframe_number for mf_ts in self.multiframe_timestamps]

    def to_stats(self) -> 'RecordingTimestampsStats':
        """
        Converts the recording timestamps to a TimestampStats object.
        This is used to generate statistics about the recording timestamps.
        """
        from skellycam.core.camera_group.timestamps.recording_timestamp_stats import RecordingTimestampsStats
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        return RecordingTimestampsStats.from_recording_timestamps(self)

    def to_mf_dataframe(self) -> pd.DataFrame:
        """
        Returns a dataframe containing the multiframe timestamps.
        Each row represents a multiframe with statistics across all cameras.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        # Create a list of MultiFrameTimestampsCSVRow objects
        csv_rows = [MultiFrameTimestampsCSVRow.from_mf_timestamps(mf_timestamps=mf_ts,
                                                                  connection_frame_number=self.frame_numbers[
                                                                      rec_number],
                                                                  recording_frame_number=rec_number,
                                                                  recording_start_time_ns=self.recording_start_time_ns,
                                                                  previous_mf_timestamps=self.multiframe_timestamps[
                                                                      rec_number - 1] if rec_number > 0 else None, )
                    for rec_number, mf_ts in enumerate(self.multiframe_timestamps)]

        # Convert each row to a dictionary and create a DataFrame
        rows_as_dicts = [row.model_dump(by_alias=True) for row in csv_rows]

        return pd.DataFrame(rows_as_dicts)


    def to_camera_dataframes(self) -> dict[CameraIdString, pd.DataFrame]:
        """
        Returns a dictionary of dataframes for each camera in the recording.
        Each dataframe contains the timestamps for that camera.
        """
        if not self.multiframe_timestamps:
            raise ValueError("No multiframe timestamps available")
        camera_dfs = {}
        for camera_id, frame_timestamps in self.timestamps_by_camera_id.items():
            # Create a list of FrameTimestampsCSVRow objects
            csv_rows = [
                FrameTimestampsCSVRow.from_frame_timestamps(
                    frame_timestamps=ts,
                    recording_frame_number=recording_frame_number,
                    connection_frame_number=self.frame_numbers[recording_frame_number],
                    recording_start_time_ns=self.recording_start_time_ns,
                    previous_frame_timestamps=frame_timestamps[
                        recording_frame_number - 1] if recording_frame_number > 0 else None
                ) for recording_frame_number, ts in enumerate(frame_timestamps)
            ]

            # Convert each row to a dictionary with aliases and create a DataFrame
            rows_as_dicts = [row.model_dump(by_alias=True) for row in csv_rows]
            camera_dfs[camera_id] = pd.DataFrame(rows_as_dicts, index=None)

        return camera_dfs

    def save_timestamps(self):
        if self.number_of_cameras == 0:
            raise ValueError("No cameras recorded. Cannot save timestamps.")
        mf_df = self.to_mf_dataframe()
        mf_df.to_csv(self.recording_info.timestamp_file_path,index=False)
        stats = self.to_stats()


        Path(self.recording_info.timestamp_stats_file_path).write_text(
            stats.model_dump_json(exclude={'sample_data'}, indent=2), encoding='utf-8')

        Path(self.recording_info.timestamp_stats_file_path).write_text(
            str(stats), encoding='utf-8')

        logger.info(
            f"Saved recording timestamps and stats to {self.recording_info.timestamps_folder} and {self.recording_info.camera_timestamps_folder}")

        dfs = self.to_camera_dataframes()
        for camera_id, camera_df in dfs.items():
            camera_df.to_csv(
                self.recording_info.camera_timestamps_file_path_from_camera_id(camera_id),
                index_label="frame_number")
        logger.info(
            f"Saved recording timestamps and stats to {self.recording_info.timestamps_folder} and {self.recording_info.camera_timestamps_folder}")



