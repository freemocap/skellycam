import time
from collections import OrderedDict
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Timestamp(BaseModel):
    start: int # nanoseconds, from time.perf_counter_ns()
    end: Optional[int] = None

class PerfCounterToUnixMapping(BaseModel):
    perf_counter_ns: int = Field(
        description="The perf_counter_ns timestamp when the mapping was created"
    )
    unix_timestamp_ns: int = Field(
        description="The unix timestamp_ns timestamp when the mapping was created"
    )

    @classmethod
    def now(cls):
        return cls(
            perf_counter_ns=time.perf_counter_ns(),
            unix_timestamp_ns=int(time.time_ns()),
        )

cla
class TimestampingBaseModel(BaseModel):
    timestamps: OrderedDict[str, Timestamp] = Field(default_factory=OrderedDict)

    def __init__(self, **data: Any):
        ts_tag = self._log_start_timestamp("init")
        super().__init__(**data)
        self._log_end_timestamp(ts_tag)

    def __setattr__(self, name: str, value: Any) -> None:
        ts_tag = self._log_start_timestamp(f"setattr_{name}")
        super().__setattr__(name, value)
        self._log_end_timestamp(ts_tag)

    def __delattr__(self, name: str) -> None:
        ts_tag = self._log_start_timestamp(f"delattr_{name}")
        super().__delattr__(name)
        self._log_end_timestamp(ts_tag)

    def __getattribute__(self, name: str) -> Any:
        attr = super().__getattribute__(name)

        if callable(attr) and not name.startswith("_"):
            def newfunc(*args, **kwargs):
                ts_tag = self._log_start_timestamp(f"call_{name}")
                result = attr(*args, **kwargs)
                self._log_end_timestamp(ts_tag)
                return result

            return newfunc
        return attr

    def _log_start_timestamp(self, tag: str) -> str:
        if tag not in self.timestamps:
            tag = tag + "_0"
        else:
            tag_num = tag.split("_")[-1]
            tag = f"{tag[:-len(tag_num)]}{int(tag_num) + 1}"
        self.timestamps[tag] = Timestamp(start=time.perf_counter_ns())
        return tag

    def _log_end_timestamp(self, tag: str) -> None:
        if tag in self.timestamps:
            self.timestamps[tag].end = time.perf_counter_ns()

    def get_timestamps(self) -> Dict[str, Timestamp]:
        return dict(self.timestamps)


if __name__ == "__main__":
    # Example usage
    class MyModel(TimestampingBaseModel):
        attribute: int

        def example_method(self):
            print("Method called")


    # Testing the updated implementation
    model = MyModel(attribute=10)
    model.attribute = 20  # This will log timestamps for setting attribute
    model.example_method()  # This will log timestamps for method call
    del model.attribute  # This will log timestamps for deleting attribute

    print(model.get_timestamps())
