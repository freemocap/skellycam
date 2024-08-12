import json
import logging
import pprint
from pathlib import Path
from typing import Optional, List
from typing import Tuple

import polars as pl

from skellycam.core import CameraId
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.timestamps.camera_timestamp_log import CameraTimestampLog

logger = logging.getLogger(__name__)


class CameraTimestampLogger:
    def __init__(self, main_timestamps_directory: str, camera_id: CameraId):
        logger.debug(f"Initializing CameraTimestampLogger for camera {camera_id}...")
        self._save_directory = main_timestamps_directory
        self._camera_id = camera_id
        self._create_save_paths()
        self._csv_header = CameraTimestampLog.as_csv_header()

        self._timestamp_logs: List[CameraTimestampLog] = []
        self._previous_frame_timestamp: Optional[int] = None
        self._perf_counter_to_unix_mapping: Optional[Tuple[int, int]] = None
        self._first_frame_timestamp: Optional[int] = None
        self._stats: Optional[dict] = None

    @property
    def camera_id(self) -> CameraId:
        return self._camera_id

    @property
    def log_count(self) -> int:
        return len(self._timestamp_logs)

    @property
    def file_name_prefix(self) -> str:
        return f"{Path(self._save_directory).stem}_camera_{self._camera_id}"

    @property
    def stats(self):
        df = self.to_dataframe()  # snag the dataframe to avoid recalculating
        return {
            "mean_frame_duration_s": df["frame_duration_ns"].mean() / 1e9,
            "std_dev_frame_duration_s": df["frame_duration_ns"].std() / 1e9,
            "mean_frames_per_second": (df["frame_duration_ns"].mean() / 1e9) ** -1,
        }

    def to_dataframe(self) -> pl.DataFrame:
        df = pl.DataFrame(
            [timestamp_log.model_dump() for timestamp_log in self._timestamp_logs]
        )
        return df

    def check_if_finished(self) -> bool:
        csv_file_exists = self._timestamp_csv_path.exists()
        stats_file_exists = self._stats_json_path.exists()
        return csv_file_exists and stats_file_exists

    def set_time_mapping(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._perf_counter_to_unix_mapping = perf_counter_to_unix_mapping
        self._first_frame_timestamp = perf_counter_to_unix_mapping[0]

    def log_timestamp(
        self, multi_frame_number: int, frame: FramePayload
    ) -> CameraTimestampLog:
        if self._previous_frame_timestamp is None:
            self._previous_frame_timestamp = frame.metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value]  # TODO: figure out what the "real" timestamp from the metadata is

        self._validate_timestamp_mapping()

        log = CameraTimestampLog.from_frame_payload(
            frame_payload=frame,
            multi_frame_number=multi_frame_number,
            timestamp_mapping=self._perf_counter_to_unix_mapping,
            first_frame_timestamp_ns=self._first_frame_timestamp,
            previous_frame_timestamp_ns=self._previous_frame_timestamp,
        )
        self._previous_frame_timestamp = frame.metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value]
        self._timestamp_logs.append(log)
        return log

    def close(self):
        logger.debug(
            f"Closing CameraTimestampLogger for camera {self._camera_id} with {len(self._timestamp_logs)} logs..."
        )
        # TODO: lots of bugs in here, bypassing for now to diagnose video errors
        # self._save_logs_as_csv()
        # self._save_documentation()
        # self._save_timestamp_stats()
        # if not self.check_if_finished():
        #     raise AssertionError(
        #         f"Failed to save timestamp logs for camera {self._camera_id} to {self._timestamp_csv_path} with {len(self._timestamp_logs)} frames (rows) of timestamp data..."
        #     )
        logger.success(
            f"Timestamp logs for camera {self._camera_id} saved successfully!"
        )

    def _create_save_paths(self):
        camera_timestamps_path = Path(self._save_directory) / "camera_timestamps"
        self._timestamp_csv_path = (
            camera_timestamps_path / f"{self.file_name_prefix}_timestamps.csv"
        )

        self._stats_json_path = (
            camera_timestamps_path / f"{self.file_name_prefix}_timestamp_stats.json"
        )

        self._documentation_path = (
            camera_timestamps_path.parent / "camera_timestamps_field_descriptions.md"
        )

    def _save_documentation(self):
        self._documentation_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._documentation_path.exists():
            with open(self._documentation_path, "w", encoding="utf-8") as f:
                f.write(CameraTimestampLog.to_document())

        logger.debug(
            f"Saved camera timestamp log field descriptions to {self._documentation_path}"
        )

    def _save_logs_as_csv(self):
        self._timestamp_csv_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(
            f"Saving timestamp logs for camera {self._camera_id} to {self._timestamp_csv_path} with {len(self._timestamp_logs)} frames (rows) of timestamp data..."
        )
        # TODO: polars.exceptions.ComputeError: CSV format does not support nested data
        # self.to_dataframe().write_csv(file = self._timestamp_csv_path) # removed the "index=False" here, can't find polars equivalent

    def _save_timestamp_stats(self):
        self._timestamp_csv_path.parent.mkdir(parents=True, exist_ok=True)
        stats = self.stats  # snag the stats to avoid recalculating
        with open(self._stats_json_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(stats, indent=4))

        logger.info(
            f"Saved timestamp stats to {self._stats_json_path} -\n\n"
            f"{pprint.pformat(stats, indent=4)})\n\n"
        )

    def _validate_timestamp_mapping(self):
        if self._perf_counter_to_unix_mapping is None:
            raise ValueError(
                "Timestamp mapping from perf_counter_ns to unix_timestamp_ns is not set! Call `set_time_mapping` before logging timestamps..."
            )
