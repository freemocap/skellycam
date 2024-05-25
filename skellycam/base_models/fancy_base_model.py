import pprint
import time
from typing import Any, Optional, OrderedDict, List, Tuple

from pydantic import BaseModel, Field


class Timestamp(BaseModel):
    name: str
    start: int  # nanoseconds, from time.perf_counter_ns()
    end: Optional[int] = None

    def __str__(self):
        if self.end is None:
            return f"{self.name}: (end timestamp not set)"
        duration_ms = (self.end - self.start) / 1e6
        return f"{self.name}: {duration_ms:.6f}ms)"


class PerfCounterToUnixMapping(BaseModel):
    """
    A mapping of the perf_counter_ns timestamp to an as-synchronous-as-possible unix timestamp_ns
    """
    perf_counter_ns: int = Field(
        description="The perf_counter_ns timestamp when the mapping was created, via `time.perf_counter_ns()`"
    )
    unix_timestamp_ns: int = Field(
        description="The unix timestamp_ns timestamp when the mapping was created, via `time.time_ns()`"
    )

    @classmethod
    def create(cls) -> 'PerfCounterToUnixMapping':
        return cls(
            perf_counter_ns=time.perf_counter_ns(),
            unix_timestamp_ns=time.time_ns(),
        )


class TimestampLogs(BaseModel):
    mapping: PerfCounterToUnixMapping = Field(default_factory=PerfCounterToUnixMapping.create)
    timestamps: OrderedDict[str, Timestamp] = Field(default_factory=OrderedDict)

    def keys(self) -> List[str]:
        return list(self.timestamps.keys())

    def values(self) -> List[Timestamp]:
        return list(self.timestamps.values())

    def items(self) -> List[Tuple[str, Timestamp]]:
        return list(self.timestamps.items())

    def __iter__(self):
        return iter(self.timestamps)

    def __getitem__(self, key):
        return self.timestamps[key]

    def __setitem__(self, key, value):
        self.timestamps[key] = value

    def __delitem__(self, key):
        del self.timestamps[key]

    def __len__(self):
        return len(self.timestamps)

    def __str__(self):
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
            def newfunc(*args, **kwargs):
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
        self.timestamps[tag] = Timestamp(name=tag, start=time.perf_counter_ns())
        return tag

    def _log_end_timestamp(self, tag: str) -> None:
        if tag in self.timestamps.keys():
            self.timestamps[tag].end = time.perf_counter_ns()

    def get_timestamps(self) -> TimestampLogs:
        return self.timestamps


class DocPrintingBaseModel(BaseModel):

    def to_descriptive_dict(self, max_length: int = 100) -> dict:
        """
        Creates a dictionary representation of the object values and includes a description of all fields of this object
        """
        descriptive_dict = {}
        descriptive_dict.update(self.model_dump())

        # truncate very long strings with internal elipses
        for key, value in descriptive_dict.items():
            if isinstance(value, str) and len(value) > max_length:
                start_str = value[:int(max_length / 2)]
                end_str = value[-int(max_length / 2):]
                descriptive_dict[key] = f"{start_str}...{end_str}"

        descriptive_dict["_field_descriptions"] = self.field_description_dict()
        return descriptive_dict

    def field_description_dict(self) -> dict:
        """
        Prints the description of all fields of this object in a dictionary {field_name: field_description}
        """
        output = {"class_name": f"{self.__class__.__name__})"}
        for field_name, field in self.__fields__.items():
            if field.description:
                output[field_name] = field.description
            else:
                output[field_name] = "No description provided"
        return output

    def docs(self) -> str:
        """
        Pretty prints a JSON-like representation of the object and its fields
        """
        return pprint.pformat(self.to_descriptive_dict(), indent=4)


class FancyBaseModel(TimestampingBaseModel, DocPrintingBaseModel):
    pass


if __name__ == "__main__":
    # Example usage
    class MyFancyModel(FancyBaseModel):
        attribute: int = Field(description="An example attribute")

        def example_method(self):
            time.sleep(0.1)
            print("Method called!")


    # Testing the updated implementation
    model = MyFancyModel(attribute=10)
    model.attribute = 20
    model.example_method()
    model.example_method()
    del model.attribute

    print("Timestamps:")
    print(model.get_timestamps())

    print("Docs:")
    print(model.docs())

    print("Field Descriptions:")
    print(pprint.pformat(model.field_description_dict(), indent=4))

    print("Descriptive Dict:")
    print(pprint.pformat(model.to_descriptive_dict(), indent=4))
