import time
from typing import Optional, OrderedDict, List, Tuple, Any, Iterator

from pydantic import BaseModel, Field

from skellycam.utilities.utc_to_perfcounter_mapping import UtcToPerfCounterMapping


class DurationTimestamps(BaseModel):
    name: str
    start: int  # nanoseconds, from time.perf_counter_ns()
    end: Optional[int] = None

    def __str__(self) -> str:
        if self.end is None:
            return f"{self.name}: (end timestamp not set)"
        duration_ms = (self.end - self.start) / 1e6
        return f"{self.name}: {duration_ms:.6f}ms)"




class TimestampLogs(BaseModel):
    mapping: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping)
    timestamps: OrderedDict[str, DurationTimestamps] = Field(default_factory=OrderedDict)

    def keys(self) -> List[str]:
        return list(self.timestamps.keys())

    def values(self) -> List[DurationTimestamps]:
        return list(self.timestamps.values())

    def items(self) -> List[Tuple[str, DurationTimestamps]]:
        return list(self.timestamps.items())

    def __iter__(self) -> Iterator[Tuple[str, DurationTimestamps]]:
        return iter(self.timestamps.items())

    def __getitem__(self, key) -> DurationTimestamps:
        return self.timestamps[key]

    def __setitem__(self, key, value) -> None:
        self.timestamps[key] = value

    def __delitem__(self, key) -> None:
        del self.timestamps[key]

    def __len__(self) -> int:
        return len(self.timestamps)

    def __str__(self) -> str:
        out_str = "Timestamps (attr_name:method:call#:duration_ms):\n\t"
        out_str += "\n\t".join([str(ts) for ts in self.timestamps.values()])
        return out_str


class TimestampingBaseModel(BaseModel):
    timestamps: TimestampLogs = Field(default_factory=TimestampLogs)

    def __init__(self, **data: Any):
        super().__init__(**data)

    def __setattr__(self, name: str, value: Any) -> None:
        ts_tag = self._log_start_timestamp(f"{name}:setattr")
        super().__setattr__(name, value)
        self._log_end_timestamp(ts_tag)

    def __delattr__(self, name: str) -> None:
        ts_tag = self._log_start_timestamp(f"{name}:delattr:")
        super().__delattr__(name)
        self._log_end_timestamp(ts_tag)

    def __getattribute__(self, name: str) -> Any:
        attr = super().__getattribute__(name)

        if callable(attr) and not name.startswith("_"):
            def newfunc(*args, **kwargs) -> Any:
                ts_tag = self._log_start_timestamp(f"{name}:call")
                result = attr(*args, **kwargs)
                self._log_end_timestamp(ts_tag)
                return result

            return newfunc
        return attr

    def _log_start_timestamp(self, tag: str) -> str:
        if tag not in self.timestamps.keys():
            tag = tag + "-0"

        while tag in self.timestamps.keys():  # duplicate tag
            tag_num = tag.split("-")[-1]
            tag = f"{tag[:-len(tag_num)]}{int(tag_num) + 1}"
        self.timestamps[tag] = DurationTimestamps(name=tag, start=time.perf_counter_ns())
        return tag

    def _log_end_timestamp(self, tag: str) -> None:
        if tag in self.timestamps.keys():
            self.timestamps[tag].end = time.perf_counter_ns()

    def get_timestamps(self) -> TimestampLogs:
        return self.timestamps
