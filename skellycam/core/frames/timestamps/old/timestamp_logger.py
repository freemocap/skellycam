import logging
from typing import List

import polars as pl
from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.timestamps.old.camera_timestamp_log import CameraTimestampLog

logger = logging.getLogger(__name__)


class CameraTimestampLogger(BaseModel):
    camera_id: CameraId
    timestamp_logs: List[CameraTimestampLog] = Field(default_factory=list)

    # self._csv_header = CameraTimestampLog.as_csv_header()

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

    def log_timestamp(
            self, multi_frame_number: int, frame: FramePayload
    ) -> CameraTimestampLog:
        log = CameraTimestampLog.from_frame_payload(
            frame_payload=frame,
            multi_frame_number=multi_frame_number,
            timestamp_mapping=self._perf_counter_to_unix_mapping,
            first_frame_timestamp_ns=self._first_frame_timestamp,
            previous_frame_timestamp_ns=self._previous_frame_timestamp,
        )
        self._timestamp_logs.append(log)
        return log
