import time

from pydantic import BaseModel, Field


class UtcToPerfCounterMapping(BaseModel):
    """
    A mapping of `time.time_ns()` to `time.perf_counter_ns()`
    to allow conversion of `time.perf_counter_ns()`'s arbitrary time base to unix time
    """
    time_time_ns: int = Field(default_factory=time.time_ns, description="UTC time in nanoseconds from `time.time_ns()`")
    time_perf_counter_ns: int = Field(default_factory=time.perf_counter_ns,
                                      description="Time in nanoseconds from `time.perf_counter_ns()` (arbirtary time base)")
