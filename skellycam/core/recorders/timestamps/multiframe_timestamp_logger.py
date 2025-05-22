import json
import logging
import pprint
from pathlib import Path
from typing import Hashable

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFrameMetadata
from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp
from skellycam.core.recorders.timestamps.multi_frame_timestamp_log import (
    MultiFrameTimestampLog,
)
from skellycam.utilities.sample_statistics import DescriptiveStatistics

logger = logging.getLogger(__name__)
from   pydantic import ConfigDict

class MultiframeTimestampLogger(BaseModel):
    multi_frame_metadatas: list[MultiFrameMetadata] = Field(default_factory=list[MultiFrameMetadata])
    csv_save_path: str
    starting_timestamp_json_path: str
    first_multi_frame_payload: MultiFramePayload | None = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,

    )

    @classmethod
    def create(cls,
               video_save_directory: str,
               recording_name: str):

        logger.debug(f"Creating MultiFrameTimestampLogger for video save directory {video_save_directory}...")
        video_save_path = Path(video_save_directory)
        video_save_path.mkdir(parents=True, exist_ok=True)

        csv_save_path = str(video_save_path / f"{recording_name}_timestamps.csv")
        starting_timestamp_json_path = str(video_save_path / f"{recording_name}_starting_timestamp.json")
        return cls(
            csv_save_path=csv_save_path,
            starting_timestamp_json_path=starting_timestamp_json_path,
            multi_frame_metadatas=[],
        )

    @property
    def camera_ids(self) -> list[str]:
        if len(self.multi_frame_metadatas) == 0:
            return []
        return list(self.multi_frame_metadatas[0].camera_ids)

    def log_multiframe(self, multi_frame_payload: MultiFramePayload):
        if len(self.multi_frame_metadatas) == 0:
            self.first_multi_frame_payload = multi_frame_payload
        self.multi_frame_metadatas.append(multi_frame_payload.to_metadata())

    def close(self):
        logger.debug(
            f"Closing timestamp logger manager... Saving timestamp logs to {self.csv_save_path}"
        )
        self._save_starting_timestamp()
        self._convert_to_dataframe_and_save()
        # self.save_timestamp_stats()
        # self.save_documentation()
        logger.success("Timestamp logs saved successfully!")

    def _save_starting_timestamp(self):
        # save starting timestamp to JSON file
        with open(self.starting_timestamp_json_path, "w", ) as f:
            f.write(
                json.dumps(
                    FullTimestamp.from_timebase_mapping(
                        self.first_multi_frame_payload.timebase_mapping).to_descriptive_dict(), indent=2)
            )

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(
            [MultiFrameTimestampLog.from_multi_frame_metadata(multi_frame_metadata=mf_metadata,
                                                              first_multi_frame_payload=self.first_multi_frame_payload).to_df_row()
             for mf_metadata in self.multi_frame_metadatas],
        )
        return df

    def _convert_to_dataframe_and_save(self):
        df = self.to_dataframe()
        df.to_csv(path_or_buf=self.csv_save_path, index=True)

        logger.info(
            f"Saved multi-frame timestamp logs to {self.csv_save_path}"
        )

    def save_timestamp_stats(self):
        stats = self._calculate_stats()

        with open(self.csv_save_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(
            f"Saved multi-frame timestamp stats to {self._stats_path} -\n\n"
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
        if not self._documentation_path.exists():
            with open(self._documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())

        logger.info(
            f"Saved multi_frame_timestamp descriptions to {self._documentation_path}"
        )

    def _calculate_stats(self) -> dict[str, object]:
        df = self.to_dataframe()  # get the dataframe to avoid recalculating

        # Basic frame rate statistics
        frame_intervals = df['timestamp_from_zero_s'].diff().dropna()
        frame_duration_stats = DescriptiveStatistics.from_samples(sample_data=frame_intervals.to_numpy(na_value=np.nan),
                                                                  name="frame_duration",
                                                                  units="seconds").model_dump()


        return frame_duration_stats
