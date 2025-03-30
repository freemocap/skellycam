# skellycam/core/recorders/timestamps/framerate_tracker.py
from collections import deque
from platform import mac_ver

import numpy as np
from pydantic import BaseModel

MAX_FRAMERATE_TRACKER_WINDOW = 1000



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
    def from_timestamps_ns(cls, timestamps_ns: list[int], framerate_source: str) -> "CurrentFramerate":
        timestamps_ms = [t / 1e6 for t in timestamps_ns]
        frame_durations_ms = [timestamps_ms[i] - timestamps_ms[i-1] for i in range(1, len(timestamps_ms))]
        frame_durations_ms.insert(0, 0)
        return cls(
            mean_frame_duration_ms=float(np.mean(frame_durations_ms)),
            mean_frames_per_second=1e3 / np.mean(frame_durations_ms) if len(frame_durations_ms) > 0 and np.mean(frame_durations_ms) > 0 else 0,
            frame_duration_max=np.max(frame_durations_ms),
            frame_duration_min=np.min(frame_durations_ms[1:]) if len(frame_durations_ms) > 1 else 0,
            frame_duration_mean=float(np.mean(frame_durations_ms)),
            frame_duration_stddev=float(np.std(frame_durations_ms)),
            frame_duration_median=float(np.median(frame_durations_ms)),
            frame_duration_coefficient_of_variation=np.std(frame_durations_ms) / np.mean(frame_durations_ms) if len(frame_durations_ms) > 0 and np.mean(frame_durations_ms) > 0 else 0,
            calculation_window_size=len(timestamps_ns),
            framerate_source=framerate_source
        )


class FramerateTrackers(BaseModel):
    backend: CurrentFramerate
    frontend: CurrentFramerate



class FramerateTracker(BaseModel):
    frames_received_timestamps_ns: deque[int]
    frame_durations_ns: deque[int]
    framerate_source: str

    @classmethod
    def create(cls, framerate_source: str, recency_window_size: int = MAX_FRAMERATE_TRACKER_WINDOW):
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
    def current_framerate(self) -> CurrentFramerate:
        return CurrentFramerate.from_timestamps_ns(list(self.frames_received_timestamps_ns), self.framerate_source)



    def to_string_list(self) -> list[str]:
        current = self.current
        return [
            f"Mean Frame Duration (ms): {current.mean_frame_duration_ms:.2f}" if current.mean_frame_duration_ms else "Mean Frame Duration (ms): N/A",
            f"Mean FPS: {current.mean_frames_per_second:.2f}" if current.mean_frames_per_second else "Mean FPS: N/A",
            f"Min Frame Duration (ms): {current.frame_duration_min:.2f}" if len(self.frame_durations_ns) > 0 else "Min Frame Duration (ms): N/A",
            f"Max Frame Duration (ms): {current.frame_duration_max:.2f}" if len(self.frame_durations_ns) > 0 else "Max Frame Duration (ms): N/A",
            f"Median Frame Duration (ms): {current.frame_duration_median:.2f}" if len(self.frame_durations_ns) > 0 else "Median Frame Duration (ms): N/A",
            f"Frame Duration Jitter (ms): {current.frame_durtation_jitter:.2f}" if len(self.frame_durations_ns) > 0 else "Frame Duration Jitter (ms): N/A",
        ]

    def __str__(self):
        return "\n".join(self.to_string_list())


if __name__ == "__main__":
    import time

    frt = FramerateTracker.create("test_source")
    max_window_size = 300
    switch_at = max_window_size // 2
    pre_switch_delay = .01
    post_switch_delay = .033
    print(f"Starting FramerateTracker test with {max_window_size} frames, starting delay {pre_switch_delay} seconds")
    swtiched_yet = False
    for i in range(300):
        if i > switch_at:
            if not swtiched_yet:
                print(f"Switching to {post_switch_delay} seconds delay")
                swtiched_yet = True
            delay = post_switch_delay
        else:
            delay = pre_switch_delay

        time.sleep(delay)
        frt.update(time.perf_counter_ns())
        if i % 10 == 0 :            # Print all the statistics at this point

            stats = frt.current
            print("\nDetailed Statistics:")
            print(f"Mean FPS: {stats.mean_frames_per_second:.2f}")
            print(f"Min Duration: {stats.frame_duration_min:.2f} ms")
            print(f"Max Duration: {stats.frame_duration_max:.2f} ms")
            print(f"Mean Duration: {stats.frame_duration_mean:.2f} ms")
            print(f"Median Duration: {stats.frame_duration_median:.2f} ms")
            print(f"Standard Deviation: {stats.frame_duration_stddev:.2f} ms")
            print(f"Coefficient of Variation: {stats.frame_duration_coefficient_of_variation:.2f}")
