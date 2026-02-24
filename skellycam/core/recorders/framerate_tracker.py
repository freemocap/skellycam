# skellycam/core/recorders/framerate_tracker.py
from collections import deque
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel

MAX_FRAMERATE_TRACKER_WINDOW = 1000
FRAMERATE_UPDATE_INTERVAL = 1.0


class CurrentFramerate(BaseModel):
    mean_frame_duration_ms: float
    mean_frames_per_second: float
    frame_duration_max: float
    frame_duration_min: float
    frame_duration_mean: float
    frame_duration_stddev: float
    frame_duration_median: float
    frame_duration_coefficient_of_variation: float
    calculation_window_size: int
    framerate_source: str = ""

    @classmethod
    def from_durations_ms(cls, durations_ms: np.ndarray, framerate_source: str) -> "CurrentFramerate":
        """Compute framerate statistics from an array of frame durations in milliseconds."""
        if len(durations_ms) < 1:
            raise ValueError(f"Need at least 1 duration to compute framerate, got {len(durations_ms)}")
        mean_dur = float(np.nanmean(durations_ms))
        if mean_dur <= 0:
            raise ValueError(f"Mean frame duration is non-positive ({mean_dur}), cannot compute framerate")
        std_dur = float(np.nanstd(durations_ms))
        return cls(
            mean_frame_duration_ms=mean_dur,
            mean_frames_per_second=1e3 / mean_dur,
            frame_duration_max=float(np.nanmax(durations_ms)),
            frame_duration_min=float(np.nanmin(durations_ms)),
            frame_duration_mean=mean_dur,
            frame_duration_stddev=std_dur,
            frame_duration_median=float(np.nanmedian(durations_ms)),
            frame_duration_coefficient_of_variation=std_dur / mean_dur,
            calculation_window_size=len(durations_ms),
            framerate_source=framerate_source,
        )

    def to_dict(self) -> dict:
        return {
            "mean_frame_duration_ms": self.mean_frame_duration_ms,
            "mean_frames_per_second": self.mean_frames_per_second,
            "frame_duration_max": self.frame_duration_max,
            "frame_duration_min": self.frame_duration_min,
            "frame_duration_mean": self.frame_duration_mean,
            "frame_duration_stddev": self.frame_duration_stddev,
            "frame_duration_median": self.frame_duration_median,
            "frame_duration_coefficient_of_variation": self.frame_duration_coefficient_of_variation,
            "calculation_window_size": self.calculation_window_size,
            "framerate_source": self.framerate_source
        }


@dataclass
class FramerateTrackers:
    backend: CurrentFramerate
    frontend: CurrentFramerate


@dataclass
class FramerateTracker:
    frame_durations_ns: deque[float]
    framerate_source: str
    _last_timestamp_ns: float | None

    @classmethod
    def create(cls, framerate_source: str, recency_window_size: int = MAX_FRAMERATE_TRACKER_WINDOW) -> "FramerateTracker":
        return cls(
            frame_durations_ns=deque(maxlen=recency_window_size),
            framerate_source=framerate_source,
            _last_timestamp_ns=None,
        )

    def update(self, timestamp_ns: float) -> None:
        if self._last_timestamp_ns is not None:
            self.frame_durations_ns.append(timestamp_ns - self._last_timestamp_ns)
        self._last_timestamp_ns = timestamp_ns

    def clear(self) -> None:
        self.frame_durations_ns.clear()
        self._last_timestamp_ns = None

    @property
    def has_data(self) -> bool:
        return len(self.frame_durations_ns) >= 1

    @property
    def current_framerate(self) -> CurrentFramerate:
        if not self.has_data:
            raise ValueError(f"No frame durations recorded yet for '{self.framerate_source}'")
        durations_ms = np.array(self.frame_durations_ns) / 1e6
        return CurrentFramerate.from_durations_ms(
            durations_ms=durations_ms,
            framerate_source=self.framerate_source,
        )

    def to_string_list(self) -> list[str]:
        current = self.current_framerate
        return [
            f"Mean Frame Duration (ms): {current.mean_frame_duration_ms:.2f}",
            f"Mean FPS: {current.mean_frames_per_second:.2f}",
            f"Min Frame Duration (ms): {current.frame_duration_min:.2f}",
            f"Max Frame Duration (ms): {current.frame_duration_max:.2f}",
            f"Median Frame Duration (ms): {current.frame_duration_median:.2f}",
            f"Frame Duration StdDev (ms): {current.frame_duration_stddev:.2f}",
        ]

    def __str__(self) -> str:
        return "\n".join(self.to_string_list())
