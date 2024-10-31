from typing import List, Optional

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.recorders.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping
from skellycam.utilities.sample_statistics import DescriptiveStatistics


class CameraFramerateStats(BaseModel):
    camera_id: CameraId
    frame_number: int = 0
    utc_mapping: UtcToPerfCounterMapping
    previous_frame_utc_ns: int

    frame_durations_ms: List[float] = []
    duration_stats: Optional[DescriptiveStatistics] = None

    max_length: int = 100

    @property
    def timestamps_unix_seconds_by_camera(self):
        return [metadata.timestamp_unix_seconds for metadata in self.recent_metadata]

    @classmethod
    def from_frame_metadata(cls,
                            frame_metadata: FrameMetadata,
                            utc_mapping: UtcToPerfCounterMapping
                            ) -> 'CameraFramerateStats':
        return cls(camera_id=frame_metadata.camera_id,
                   frame_number=frame_metadata.frame_number,
                   previous_frame_utc_ns=utc_mapping.convert_perf_counter_ns_to_unix_ns(
                       perf_counter_ns=frame_metadata.timestamp_ns),
                   utc_mapping=utc_mapping)

    def add_frame_metadata(self, frame_metadata: FrameMetadata):
        utc_timestamp_ns = self.utc_mapping.convert_perf_counter_ns_to_unix_ns(
            perf_counter_ns=frame_metadata.timestamp_ns)
        frame_duration_ns = utc_timestamp_ns - self.previous_frame_utc_ns
        self.previous_frame_utc_ns = utc_timestamp_ns
        self.frame_durations_ms.append(frame_duration_ns / 1e6)
        if len(self.frame_durations_ms) > self.max_length:
            self.frame_durations_ms.pop(0)

        if len(self.frame_durations_ms) < 30:
            return None

        self.duration_stats = DescriptiveStatistics.from_samples(
            name=f"Camera-{self.camera_id} Frame Duration Statistics",
            sample_data=self.frame_durations_ms)

    @property
    def duration_mean_std_ms_str(self):
        if self.duration_stats is None:
            return "N/A"
        return f"{self.duration_stats.mean:.2f}({self.duration_stats.standard_deviation:.2f})ms"

    @property
    def fps_mean_str(self):
        if self.duration_stats is None:
            return "N/A"
        return f"{1 / (self.duration_stats.mean * .001):.2f}"
