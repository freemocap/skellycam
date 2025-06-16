import time
from datetime import datetime

import numpy as np
from pydantic import BaseModel, Field
from tzlocal import get_localzone

from skellycam.core.types.numpy_record_dtypes import TIMEBASE_MAPPING_DTYPE


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

    def to_numpy_record_array(self) -> TIMEBASE_MAPPING_DTYPE:
        return np.rec.array(
            (self.utc_time_ns, self.perf_counter_ns, self.local_time_utc_offset),
            dtype=TIMEBASE_MAPPING_DTYPE
        )

    @classmethod
    def from_numpy_record_array(cls, rec_array: np.recarray):
        if rec_array.dtype != TIMEBASE_MAPPING_DTYPE:
            raise ValueError(f"Expected rec_array to have dtype {TIMEBASE_MAPPING_DTYPE}, but got {rec_array.dtype}")
        return cls(
            utc_time_ns=int(rec_array.utc_time_ns.copy()),
            perf_counter_ns=int(rec_array.perf_counter_ns.copy()),
            local_time_utc_offset=int(rec_array.local_time_utc_offset.copy())
        )

