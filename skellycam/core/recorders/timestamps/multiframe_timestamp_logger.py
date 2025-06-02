import json
import logging
import pprint
from pathlib import Path
from typing import Hashable

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload, MultiFrameMetadata
from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp
from skellycam.core.recorders.timestamps.multi_frame_timestamp_log import (
    MultiFrameTimestampLog,
)
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.utilities.sample_statistics import DescriptiveStatistics

logger = logging.getLogger(__name__)
from pydantic import ConfigDict


class MultiframeTimestampLogger(BaseModel):
    recording_info: RecordingInfo
    initial_multi_frame_payload: MultiFramePayload
    multi_frame_metadatas: list[MultiFrameMetadata] = []

    model_config = ConfigDict(
        arbitrary_types_allowed=True,

    )

    @property
    def timestamps_base_path(self) -> str:
        path= Path(self.recording_info.timestamps_folder)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def csv_save_path(self) -> str:
        return str(Path(self.recording_info.timestamps_folder)/ f"{self.recording_info.recording_name}_timestamps.csv")

    @property
    def starting_timestamp_json_path(self) -> str:
        return str(Path(self.recording_info.timestamps_folder)/ f"{self.recording_info.recording_name}_starting_timestamp.json")

    @property
    def stats_path(self) -> str:
        return str(Path(self.timestamps_base_path)/ f"{self.recording_info.recording_name}_timestamps_stats.json")

    @property
    def documentation_path(self) -> str:
        return str(Path(self.timestamps_base_path)/ f"{self.recording_info.recording_name}_timestamps_README.md")

    def log_multiframe(self, multi_frame_payload: MultiFramePayload):
        if len(self.multi_frame_metadatas) == 0:
            self.initial_multi_frame_payload = multi_frame_payload
        self.multi_frame_metadatas.append(multi_frame_payload.to_metadata())

    def close(self):
        logger.debug(
            f"Closing timestamp logger manager... Saving timestamp logs to {self.csv_save_path}"
        )
        self._save_starting_timestamp()
        self._convert_to_dataframe_and_save()
        self.save_stats()
        self.save_documentation()
        logger.success("Timestamp logs saved successfully!")

    def _save_starting_timestamp(self):
        # save starting timestamp to JSON file
        with open(self.starting_timestamp_json_path, "w", ) as f:
            f.write(
                json.dumps(
                    FullTimestamp.from_timebase_mapping(
                        self.initial_multi_frame_payload.timebase_mapping).to_descriptive_dict(), indent=2)
            )

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(
            [MultiFrameTimestampLog.from_multi_frame_metadata(multi_frame_metadata=mf_metadata,
                                                              initial_multi_frame_payload=self.initial_multi_frame_payload).to_df_row()
             for mf_metadata in self.multi_frame_metadatas],
        )
        return df

    def _convert_to_dataframe_and_save(self):
        df = self.to_dataframe()
        df.to_csv(path_or_buf=self.csv_save_path, index=True)

        logger.info(
            f"Saved multi-frame timestamp logs to {self.csv_save_path}"
        )

    def save_stats(self):
        stats = self._calculate_stats()

        with open(self.stats_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(
            f"Saved multi-frame timestamp stats to {self.stats_path} -\n\n"
            f"{pprint.pformat(stats, indent=4)})\n\n"
        )

    def _get_camera_stats(self) -> dict[Hashable, dict[str, float]]:
        camera_stats_by_id = {}
        try:
            for camera_id, timestamp_logger in self._timestamp_loggers.items():
                if timestamp_logger.stats is None:
                    raise AssertionError(
                        "Timestamp logger stats are None, but `close` was called! Theres a buggo in the logic somewhere..."
                    )
                camera_stats_by_id[camera_id] = timestamp_logger.stats

        except Exception as e:
            logger.error(f"Error saving timestamp stats: {e}")
            raise
        return camera_stats_by_id

    def save_documentation(self):
        with open(self.documentation_path, "w") as f:
            f.write(MultiFrameTimestampLog.to_document())

        logger.info(
            f"Saved multi_frame_timestamp descriptions to {self.documentation_path}"
        )

    def _calculate_stats(self) -> dict[str, object]:
        df = self.to_dataframe()  # get the dataframe to avoid recalculating

        # Basic frame rate statistics
        frame_intervals = df['timestamp_from_zero_s'].diff().dropna()
        return dict(
            framerate_stats=DescriptiveStatistics.from_samples(
                sample_data=frame_intervals.to_numpy(na_value=np.nan)**-1,
                name="frame_duration",
                units="milliseconds").to_dict(),
            frame_duration_stats=DescriptiveStatistics.from_samples(
                sample_data=frame_intervals.to_numpy(na_value=np.nan),
                name="frame_duration",
                units="milliseconds").to_dict(),
            finter_camera_timestamp_range_stats_ms=DescriptiveStatistics.from_samples(
                sample_data=df['inter_camera_timestamp_range_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="inter_camera_timestamp_range_ns",
                units="milliseconds").to_dict(),
            time_before_grab_signal_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_before_grab_signal_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_before_grab_signal",
                units="milliseconds").to_dict(),
            time_spent_grabbing_frame_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_grabbing_frame_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_grabbing_frame",
                units="milliseconds").to_dict(),
            time_waiting_to_retrieve_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_waiting_to_retrieve_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_waiting_to_retrieve",
                units="milliseconds").to_dict(),
            time_spent_retrieving_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_retrieving_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_retrieving",
                units="milliseconds").to_dict(),
            time_spent_waiting_to_be_put_into_camera_shm_buffer_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_waiting_to_be_put_into_camera_shm_buffer_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_waiting_to_be_put_into_camera_shm_buffer",
                units="milliseconds").to_dict(),
            time_spent_in_camera_shm_buffer_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_in_camera_shm_buffer_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_in_camera_shm_buffer",
                units="milliseconds").to_dict(),
            time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer",
                units="milliseconds").to_dict(),
            time_spent_in_multi_frame_escape_shm_buffer_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_in_multi_frame_escape_shm_buffer_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_in_multi_frame_escape_shm_buffer",
                units="milliseconds").to_dict(),
            time_spent_waiting_to_start_compress_to_jpeg_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_waiting_to_start_compress_to_jpeg_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_waiting_to_start_compress_to_jpeg",
                units="milliseconds").to_dict(),
            time_spent_in_compress_to_jpeg_stats=DescriptiveStatistics.from_samples(
                sample_data=df['mean_time_spent_in_compress_to_jpeg_ns'].to_numpy(na_value=np.nan) / 1e6,
                name="time_spent_in_compress_to_jpeg",
                units="milliseconds").to_dict(),
        )
