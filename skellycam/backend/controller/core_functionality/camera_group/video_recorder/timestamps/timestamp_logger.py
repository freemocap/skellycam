import json
import pprint
from pathlib import Path
from typing import Optional, List
from typing import Tuple

import pandas as pd

from skellycam.system.environment.get_logger import logger
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload
from skellycam.models.timestamps.camera_timestamp_log import CameraTimestampLog


class CameraTimestampLogger:
    def __init__(self, main_timestamps_directory: str, camera_id: CameraId):
        self._save_directory = main_timestamps_directory
        self._camera_id = camera_id
        self._create_timestamp_csv_path()
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
    def finished(self):
        csv_file_exists = self._timestamp_csv_path.exists()
        stats_file_exists = self._stats_json_path.exists()
        return csv_file_exists and stats_file_exists

    @property
    def file_name_prefix(self) -> str:
        return f"{Path(self._save_directory).stem}_camera_{self._camera_id}"

    @property
    def stats(self) -> Optional[dict]:
        return self._stats

    def set_time_mapping(self, perf_counter_to_unix_mapping: Tuple[int, int]):
        self._perf_counter_to_unix_mapping = perf_counter_to_unix_mapping
        self._first_frame_timestamp = perf_counter_to_unix_mapping[0]

    def log_timestamp(self, multi_frame_number: int, frame: FramePayload) -> CameraTimestampLog:
        if self._previous_frame_timestamp is None:
            self._previous_frame_timestamp = frame.timestamp_ns
        log = CameraTimestampLog.from_frame_payload(frame_payload=frame,
                                                    timestamp_mapping=self._perf_counter_to_unix_mapping,
                                                    first_frame_timestamp_ns=self._first_frame_timestamp,
                                                    multi_frame_number=multi_frame_number,
                                                    previous_frame_timestamp_ns=self._previous_frame_timestamp)
        self._previous_frame_timestamp = frame.timestamp_ns
        self._timestamp_logs.append(log)
        return log

    def _create_timestamp_csv_path(self):
        camera_timestamps_path = Path(self._save_directory) / "camera_timestamps"
        self._timestamp_csv_path = camera_timestamps_path / f"{self.file_name_prefix}_timestamps.csv"

    def _save_documentation(self):
        documentation_path = self._timestamp_csv_path.parent.parent / "camera_timestamps_field_descriptions.md"
        if not documentation_path.exists():
            with open(documentation_path, "w") as f:
                f.write(CameraTimestampLog.to_document())

    def close(self):
        self._save_logs_as_csv()
        self._save_documentation()
        self._save_timestamp_stats()

    def _save_logs_as_csv(self):
        self._timestamp_csv_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp_df = pd.DataFrame([timestamp_log.dict() for timestamp_log in self._timestamp_logs])
        timestamp_df.to_csv(self._timestamp_csv_path, index=False)

    def _save_timestamp_stats(self):
        self._stats = self._get_stats_from_csv()
        self._stats_json_path = self._timestamp_csv_path.parent / f"{self.file_name_prefix}_timestamp_stats.json"
        with open(self._stats_json_path, "w") as f:
            f.write(json.dumps(self._stats, indent=4))

        logger.info(f"Saved timestamp stats to {self._stats_json_path} -\n\n"
                    f"{pprint.pformat(self._stats, indent=4)})\n\n")


    def _get_stats_from_csv(self):
        timestamps_df = pd.read_csv(self._timestamp_csv_path)
        return {"mean_frame_duration_s": timestamps_df["frame_duration_ns"].mean() / 1e9,
                "std_dev_frame_duration_s": timestamps_df["frame_duration_ns"].std() / 1e9,
                "mean_frames_per_second": (timestamps_df["frame_duration_ns"].mean() / 1e9) ** -1}
