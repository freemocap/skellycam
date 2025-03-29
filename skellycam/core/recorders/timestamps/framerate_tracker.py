from collections import deque
from typing import List

from pydantic import BaseModel




class CurrentFramerate(BaseModel):
    mean_frame_duration_ms: float|None
    mean_frames_per_second: float|None
    calculation_window_size: int
    framerate_source: str


class FramerateTrackers(BaseModel):
    backend: CurrentFramerate
    frontend: CurrentFramerate

MAX_FRAMERATE_TRACKER_WINDOW = 300
class FramerateTracker(BaseModel):
    frames_received_timestamps_ns: deque[int]
    frame_durations_ns: deque[int]
    framerate_source: str

    @classmethod
    def create(cls, framerate_source:str, recency_window_size: int = MAX_FRAMERATE_TRACKER_WINDOW):
        return cls(frames_received_timestamps_ns=deque(maxlen=recency_window_size),
                   frame_durations_ns=deque(maxlen=recency_window_size),
                   framerate_source=framerate_source)


    def update(self, timestamp_ns: int) -> None:
        if not isinstance(timestamp_ns, int):
            raise ValueError("Use `time.perf_counter_ns()`, coward")
        self.frames_received_timestamps_ns.append(timestamp_ns)

        if len(self.frames_received_timestamps_ns) > 1:
            self.frame_durations_ns.append(
                self.frames_received_timestamps_ns[-1] - self.frames_received_timestamps_ns[-2]
            )

    @property
    def mean_frame_duration_ms(self) -> float|None:
        if len(self.frame_durations_ns) == 0:
            return None
        return sum(self.frame_durations_ns) / len(self.frame_durations_ns) / 1e6

    @property
    def mean_frames_per_second(self) -> float|None:
        if self.mean_frame_duration_ms is None:
            return None
        return 1e3 / self.mean_frame_duration_ms

    @property
    def current(self) -> CurrentFramerate:
        return CurrentFramerate(
            mean_frame_duration_ms=self.mean_frame_duration_ms,
            mean_frames_per_second=self.mean_frames_per_second,
            calculation_window_size=len(self.frames_received_timestamps_ns),
            framerate_source=self.framerate_source
        )

    def to_string_list(self) -> List[str]:
        return [
            f"Mean Frame Duration (ms): {self.mean_frame_duration_ms:.2f}",
            f"Mean FPS: {self.mean_frames_per_second:.2f}",
            f"Recent FPS: {self.recent_frames_per_second:.2f}",
            f"Recent Mean Frame Duration (ms): {self.recent_mean_frame_duration_ms:.2f}",
        ]
    def __str__(self):
        return "\n".join(self.to_string_list())


if __name__ == "__main__":
    import time

    frt = FramerateTracker.create(30)
    for i in range(300):
        if i > 50:
            delay = .033
        else:
            delay = .01

        time.sleep(delay)
        frt.update(time.perf_counter_ns())
        if i % 10 == 0 and frt.mean_frame_duration_ms and frt.mean_frames_per_second:
            print(
                f"Frame #{i} (delay: {delay}) - Mean FPS: {frt.mean_frames_per_second:.3f}, Mean Frame Duration: {frt.mean_frame_duration_ms:.3f} ms")