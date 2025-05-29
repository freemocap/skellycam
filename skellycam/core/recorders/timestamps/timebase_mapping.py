import time
from datetime import datetime

import numpy as np
from pydantic import BaseModel, Field
from tzlocal import get_localzone


def get_utc_offset() -> int:
    return int(datetime.now(get_localzone()).utcoffset().total_seconds())

class TimeBaseMapping(BaseModel):
    """
    A mapping of `time.time_ns()` to `time.perf_counter_ns()`
    to allow conversion of `time.perf_counter_ns()`'s arbitrary time base to unix time
    """
    utc_time_ns: int = Field(default_factory=time.time_ns, description="UTC time in nanoseconds from `time.time_ns()`")
    perf_counter_ns: int = Field(default_factory=time.perf_counter_ns,
                                 description="Time in nanoseconds from `time.perf_counter_ns()` (arbirtary time base)")
    local_time_utc_offset: int = Field(default_factory=get_utc_offset, description="Local time GMT offset in seconds")
    def convert_perf_counter_ns_to_unix_ns(self, perf_counter_ns: int, local_time: bool) -> int:
        """
        Convert a `time.perf_counter_ns()` timestamp to a unix timestamp
        """
        if local_time:
            return int(self.utc_time_ns + (perf_counter_ns - self.perf_counter_ns) + (self.local_time_utc_offset * 1e9))
        return self.utc_time_ns + (perf_counter_ns - self.perf_counter_ns)

    def to_numpy_buffer(self):
        return np.concatenate([np.array([self.utc_time_ns]), np.array([self.perf_counter_ns])], dtype=np.int64)

    @classmethod
    def from_numpy_buffer(cls, buffer: np.ndarray):
        return cls(utc_time_ns=buffer[0], perf_counter_ns=buffer[1])
