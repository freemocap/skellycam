import json
import logging
import pprint
from pathlib import Path
from typing import Dict, List, Any, Hashable, Optional

import pandas as pd
from pydantic import BaseModel, Field

from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFrameMetadata
from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp
from skellycam.core.recorders.timestamps.old.multi_frame_timestamp_log import (
    MultiFrameTimestampLog,
)

logger = logging.getLogger(__name__)


class MultiframeTimestampLogger(BaseModel):
    multi_frame_metadatas: List[MultiFrameMetadata] = Field(default_factory=List[MultiFrameMetadata])
    starting_frame_full_timestamp: Optional[FullTimestamp] = None
    csv_save_path: str
    starting_timestamp_json_path: str

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

    def log_multiframe(self, multi_frame_payload: MultiFramePayload):
        if len(self.multi_frame_metadatas) == 0:
            self.starting_frame_full_timestamp = FullTimestamp.from_perf_to_unix_mapping(
                multi_frame_payload.utc_ns_to_perf_ns)
        self.multi_frame_metadatas.append(multi_frame_payload.to_metadata())

    def close(self):
        logger.debug(
            f"Closing timestamp logger manager... Saving timestamp logs to {self.csv_save_path}"
        )
        self._save_starting_timestamp()
        self._convert_to_dataframe_and_save()

        logger.success("Timestamp logs saved successfully!")

    def _save_starting_timestamp(self):
        # save starting timestamp to JSON file
        with open(self.starting_timestamp_json_path, "w", ) as f:
            f.write(
                json.dumps(self.starting_frame_full_timestamp.to_descriptive_dict(), indent=4)
            )

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(
            [mf_metadata.to_df_row() for mf_metadata in self.multi_frame_metadatas]
        )
        return df

    def _convert_to_dataframe_and_save(self):
        df = self.to_dataframe()
        df.to_csv(path_or_buf=self.csv_save_path, index=True)
        logger.info(
            f"Saved multi-frame timestamp logs to {self.csv_save_path}"
        )

    def save_timestamp_stats(self):
        stats = self._get_timestamp_stats()

        stats["timestamp_stats_by_camera_id"] = self._get_camera_stats(stats)

        with open(self._stats_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(stats, indent=4))

        self.save_documentation()

        logger.info(
            f"Saved multi-frame timestamp stats to {self._stats_path} -\n\n"
            f"{pprint.pformat(stats, indent=4)})\n\n"
        )

    def _get_camera_stats(self, stats) -> Dict[Hashable, Dict[str, float]]:
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

    def _get_timestamp_stats(self) -> Dict[Hashable, Any]:
        stats = {
            "total_frames": len(self.multi_frame_metadatas),
            "total_recording_duration_s": self.multi_frame_metadatas[
                -1
            ].seconds_since_cameras_connected,
        }
        stats.update(self._calculate_stats())
        return stats

    def _calculate_stats(self) -> Dict[str, Any]:
        df = self.to_dataframe()  # get the dataframe to avoid recalculating
        return {
            "todo:addstats", "todo:addstats"
            # "mean_frame_duration_s": df["mean_frame_duration_s"].mean(),
            # "std_frame_duration_s": df["mean_frame_duration_s"].std(),
            # "mean_frames_per_second": df["mean_frame_duration_s"].mean() ** -1,
            # "mean_inter_camera_timestamp_range_s": df[
            #     "inter_camera_timestamp_range_s"
            # ].mean(),
            # "std_dev_inter_camera_timestamp_range_s": df[
            #     "inter_camera_timestamp_range_s"
            # ].std(),
            # "mean_inter_camera_timestamp_stddev_s": df[
            #     "inter_camera_timestamp_stddev_s"
            # ].mean(),
            # "std_dev_inter_camera_timestamp_stddev_s": df[
            #     "inter_camera_timestamp_stddev_s"
            # ].std(),
        }

    def save_documentation(self):
        if not self._documentation_path.exists():
            with open(self._documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())

        logger.info(
            f"Saved multi_frame_timestamp descriptions to {self._documentation_path}"
        )
