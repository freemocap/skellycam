from typing import List

from pydantic import BaseModel, ConfigDict, Field

class CurrentFrameRate(BaseModel):
    mean_frame_duration_ms: float
    mean_frames_per_second: float
    recent_frames_per_second: float
    recent_mean_frame_duration_ms: float

class FrameRateTracker(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frames_received_timestamps_ns: List[int] = Field(default_factory=list)
    frame_durations_ns: List[int] = Field(default_factory=list)

    # calculate these as running values to avoid needing to recalculate every time from an ever-growing list
    running_sum_frame_duration_ns: int = 0

    # We can calcualte the recent values on the fly because its fixed size
    recency_window: int = 100  # number of frames to consider for recent frame rate, 100 frames is 3.33 seconds at 30fps

    def update(self, timestamp_ns: int) -> None:
        if not isinstance(timestamp_ns, int):
            raise ValueError("Use `time.perf_counter_ns()`, coward")
        self.frames_received_timestamps_ns.append(timestamp_ns)

        if len(self.frames_received_timestamps_ns) > 1:
            self.frame_durations_ns.append(
                self.frames_received_timestamps_ns[-1] - self.frames_received_timestamps_ns[-2]
            )
            self.running_sum_frame_duration_ns += self.frame_durations_ns[-1]


    @property
    def mean_frame_duration_ms(self) -> float:
        if len(self.frame_durations_ns) < 1:
            return -1
        return (self.running_sum_frame_duration_ns / len(self.frame_durations_ns)) / 1e6

    @property
    def mean_frames_per_second(self) -> float:
        if len(self.frame_durations_ns) < 2:
            return -1
        return 1e3 / self.mean_frame_duration_ms

    @property
    def recent_frames_per_second(self) -> float:
        if len(self.frame_durations_ns) < self.recency_window:
            return self.mean_frames_per_second
        recent_durations_ns = self.frame_durations_ns[-self.recency_window:]
        return 1e3 / (sum(recent_durations_ns) / len(recent_durations_ns) / 1e6)

    @property
    def recent_mean_frame_duration_ms(self) -> float:
        if len(self.frame_durations_ns) < self.recency_window:
            return self.mean_frame_duration_ms
        recent_durations = self.frame_durations_ns[-self.recency_window:]
        return sum(recent_durations) / len(recent_durations) / 1e6

    def current(self) -> CurrentFrameRate:
        return CurrentFrameRate(
            mean_frame_duration_ms = self.mean_frame_duration_ms,
            mean_frames_per_second = self.mean_frames_per_second,
            recent_frames_per_second = self.recent_frames_per_second,
            recent_mean_frame_duration_ms = self.recent_mean_frame_duration_ms,
        )

if __name__ == "__main__":
    import time

    frt = FrameRateTracker()
    for i in range(200):
        if i > 50:
            delay=.033
        else:
            delay=.01

        time.sleep(delay)
        frt.update(time.perf_counter_ns())
        print(f"Frame#{i} (delay: {delay}) -  Mean FPS: {frt.mean_frames_per_second}, Recent FPS: {frt.recent_frames_per_second}, Mean Frame Duration: {frt.mean_frame_duration_ms}ms, Recent Frame Duration: {frt.recent_mean_frame_duration_ms}ms")
