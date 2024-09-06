import json
import logging
import pprint
from pathlib import Path
from typing import Dict, Tuple, List, Any, Hashable

import pandas as pd
from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFrameMetadata
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.core.timestamps.old.camera_timestamp_log import CameraTimestampLog
from skellycam.core.timestamps.old.multi_frame_timestamp_log import (
    MultiFrameTimestampLog,
)

logger = logging.getLogger(__name__)


class MultiframeTimestampLogger(BaseModel):
    multi_frame_metadatas: List[MultiFrameMetadata] = Field(default_factory=list)
    csv_save_path: str

    @classmethod
    def from_first_multiframe(cls,
                              first_multiframe: MultiFramePayload,
                              video_save_directory: str,
                              recording_name: str):
        """
        NOTE - Does not add `first mf payload` timestamps to logsos - call `log multiframe` after creation
        """
        logger.debug(f"Creating MultiFrameTimestampLogger for video save directory {video_save_directory}...")
        video_save_path = Path(video_save_directory)
        if not video_save_path.exists():
            raise FileNotFoundError(f"Video save directory {video_save_directory} does not exist!")

        csv_save_path = str(video_save_path / f"{recording_name}_timestamps.csv")

        # documentation_path = str(video_save_path / f"{recording_name}_timestamps_README.md")
        #
        # timestamp_stats_path = str(video_save_path / f"{recording_name}_timestamp_stats.json")

        csv_header = MultiFrameTimestampLog.as_csv_header(
            camera_ids=first_multiframe.camera_ids
        )
        return cls(
            csv_save_path=csv_save_path,
            multi_frame_metadatas=[],
        )

    def log_multiframe(self, multi_frame_payload: MultiFramePayload):
        self.multi_frame_metadatas.append(multi_frame_payload.to_metadata())

    def check_if_finished(self):
        all_loggers_finished = all(
            [
                timestamp_logger.check_if_finished()
                for timestamp_logger in self._timestamp_loggers.values()
            ]
        )
        timestamp_csv_exists = self.csv_save_path.exists()
        timestamp_stats_exists = self._stats_path.exists()
        return all_loggers_finished and timestamp_csv_exists and timestamp_stats_exists

    def set_time_mapping(
            self, start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int]
    ):
        logger.debug(
            f"Setting (`perf_coutner_ns`:`unix_time_ns`) time mapping: {start_time_perf_counter_ns_to_unix_mapping}..."
        )
        self._start_time_perf_counter_ns_to_unix_mapping = (
            start_time_perf_counter_ns_to_unix_mapping
        )
        self._save_starting_timestamp(self._start_time_perf_counter_ns_to_unix_mapping)

        self._first_frame_timestamp = self._start_time_perf_counter_ns_to_unix_mapping[
            0
        ]
        for timestamp_logger in self._timestamp_loggers.values():
            timestamp_logger.set_time_mapping(
                self._start_time_perf_counter_ns_to_unix_mapping
            )

    def handle_multi_frame_payload(
            self, multi_frame_payload: MultiFramePayload, multi_frame_number: int
    ):
        timestamp_log_by_camera = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            timestamp_log_by_camera[camera_id] = self._timestamp_loggers[
                camera_id
            ].log_timestamp(frame=frame, multi_frame_number=multi_frame_number)
        self._log_main_timestamp(
            timestamp_log_by_camera, multi_frame_number=multi_frame_number
        )

    def close(self):
        logger.debug(
            f"Closing timestamp logger manager... Saving timestamp logs to {self.csv_save_path}"
        )

        self._convert_to_dataframe_and_save()
        # self._save_documentation()
        # self._save_timestamp_stats()
        # if not self.check_if_finished():
        #     raise AssertionError(
        #         "Failed to save timestamp logs for all cameras to CSV and JSON files!"
        #     )

        logger.success("Timestamp logs saved successfully!")

    def _save_starting_timestamp(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._starting_timestamp = FullTimestamp.from_perf_to_unix_mapping(perf_counter_to_unix_mapping)
        # save starting timestamp to JSON file
        with open(
                self._starting_timestamp_json_path,
                "w",
        ) as f:
            f.write(
                json.dumps(self._starting_timestamp.to_descriptive_dict(), indent=4)
            )

    def _log_main_timestamp(
            self,
            timestamp_log_by_camera: Dict[CameraId, CameraTimestampLog],
            multi_frame_number: int,
    ):
        multi_frame_timestamp_log = MultiFrameTimestampLog.from_timestamp_logs(
            timestamp_logs=timestamp_log_by_camera,
            timestamp_mapping=self._start_time_perf_counter_ns_to_unix_mapping,
            first_frame_timestamp_ns=self._first_frame_timestamp,
            multi_frame_number=multi_frame_number,
        )
        self._multi_frame_timestamp_logs.append(multi_frame_timestamp_log)

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(
            [mf_metadata.model_dump() for mf_metadata in self.multi_frame_metadatas]
        )
        return df

    def _convert_to_dataframe_and_save(self):
        df = self.to_dataframe()
        df.to_csv(path_or_buf=self.csv_save_path, index=True)
        logger.info(
            f"Saved multi-frame timestamp logs to {self.csv_save_path}"
        )

    def _save_timestamp_stats(self):
        stats = self._get_timestamp_stats()

        stats["timestamp_stats_by_camera_id"] = self._get_camera_stats(stats)

        with open(self._stats_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(stats, indent=4))

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
            "total_frames": len(self._multi_frame_timestamp_logs),
            "total_recording_duration_s": self._multi_frame_timestamp_logs[
                -1
            ].mean_timestamp_from_zero_s,
            "start_time_perf_counter_ns_to_unix_mapping": {
                "time.perf_counter_ns": self._start_time_perf_counter_ns_to_unix_mapping[
                    0
                ],
                "time.time_ns": self._start_time_perf_counter_ns_to_unix_mapping[1],
            },
        }
        stats.update(self._calculate_stats())
        return stats

    def _calculate_stats(self) -> Dict[str, float]:
        df = self.to_dataframe()  # get the dataframe to avoid recalculating
        return {
            "mean_frame_duration_s": df["mean_frame_duration_s"].mean(),
            "std_frame_duration_s": df["mean_frame_duration_s"].std(),
            "mean_frames_per_second": df["mean_frame_duration_s"].mean() ** -1,
            "mean_inter_camera_timestamp_range_s": df[
                "inter_camera_timestamp_range_s"
            ].mean(),
            "std_dev_inter_camera_timestamp_range_s": df[
                "inter_camera_timestamp_range_s"
            ].std(),
            "mean_inter_camera_timestamp_stddev_s": df[
                "inter_camera_timestamp_stddev_s"
            ].mean(),
            "std_dev_inter_camera_timestamp_stddev_s": df[
                "inter_camera_timestamp_stddev_s"
            ].std(),
        }

    def _save_documentation(self):
        if not self._documentation_path.exists():
            with open(self._documentation_path, "w") as f:
                f.write(MultiFrameTimestampLog.to_document())

        logger.info(
            f"Saved multi_frame_timestamp descriptions to {self._documentation_path}"
        )
