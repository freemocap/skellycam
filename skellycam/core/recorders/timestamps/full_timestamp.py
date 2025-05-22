import calendar
import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from tzlocal import get_localzone

from skellycam.core.recorders.timestamps.timebase_mapping import TimeBaseMapping


class FullTimestamp(BaseModel):
    """
    The world's most extravagant timestamp object

    If you manage to come up with a timestamp-related use case that isn't covered by this bad boi, let me know and we'll add it
    """

    unix_timestamp_utc: float = Field(
        description="The unix timestamp in UTC, i.e. seconds since 1970-01-01 00:00:00 UTC"
    )
    unix_timestamp_local: float = Field(
        description="The unix timestamp in the local timezone where the timestamp was logged, i.e. seconds since 1970-01-01 00:00:00 in the local timezone"
    )
    unix_timestamp_utc_isoformat: str = Field(
        description="The UTC timestamp in ISO format, i.e. 1970-01-01T00:00:00+00:00"
    )
    unix_timestamp_local_isoformat: str = Field(
        description="The local timestamp in ISO format, i.e. 1970-01-01T00:00:00+[local timezone offset in HH:MM]"
    )
    local_time_zone: str = Field(
        description="The local timezone where the timestamp was logged, i.e. Europe/Berlin"
    )
    human_friendly_utc: str = Field(
        description="The UTC timestamp in human-friendly format, i.e. 1970-01-01 00:00:00.000000"
    )
    human_friendly_local: str = Field(
        description="The local timestamp in human-friendly format, i.e. 1970-01-01 00:00:00.000000"
    )
    day_of_week: str = Field(description="The day of the week, i.e. Monday")
    calendar_week: int = Field(
        description="The calendar week, i.e. 1 for the first week of the year"
    )
    day_of_year: int = Field(
        description="The day of the year, i.e. 1 for the first day of the year"
    )
    is_leap_year: bool = Field(
        description="Whether or not the year of the timestamp is a leap year"
    )

    perf_counter_ns: int = Field(
        description="The perf_counter_ns timestamp when the Timestamp object was created, if available (this is an abitrary timebase, but may be used to map a perf_counter_ns timestamp to a system-clock unix timestamp)"
    )

    @classmethod
    def from_datetime(cls, datetime_reference: datetime, perf_counter_ns: int):
        date_time_utc = datetime_reference.astimezone(timezone.utc)
        date_time_local = datetime_reference.astimezone(get_localzone())

        return cls(
            unix_timestamp_utc=date_time_utc.timestamp(),
            unix_timestamp_local=date_time_local.timestamp(),
            unix_timestamp_utc_isoformat=date_time_utc.isoformat(),
            unix_timestamp_local_isoformat=date_time_local.isoformat(),
            local_time_zone=str(get_localzone()),
            human_friendly_utc=date_time_utc.strftime("%Y-%m-%d %H:%M:%S.%f"),
            human_friendly_local=date_time_local.strftime("%Y-%m-%d %H:%M:%S.%f"),
            day_of_week=calendar.day_name[date_time_local.weekday()],
            calendar_week=date_time_local.isocalendar()[1],
            day_of_year=date_time_local.timetuple().tm_yday,
            is_leap_year=calendar.isleap(date_time_local.year),
            perf_counter_ns=perf_counter_ns,
        )

    @classmethod
    def now(cls):
        return cls.from_datetime(datetime.now(), perf_counter_ns=time.perf_counter_ns())

    @classmethod
    def from_timebase_mapping(cls, utc_to_perf_mapping: TimeBaseMapping):
        # Convert perf_counter_ns to seconds and add to the base UTC timestamp
        base_utc_timestamp = utc_to_perf_mapping.utc_time_ns / 1e9
        perf_counter_seconds = utc_to_perf_mapping.perf_counter_ns / 1e9
        datetime_reference = datetime.fromtimestamp(base_utc_timestamp + perf_counter_seconds)

        return cls.from_datetime(
            datetime_reference,
            perf_counter_ns=utc_to_perf_mapping.perf_counter_ns,
        )

    @property
    def utc(self) -> float:
        return self.unix_timestamp_utc

    def __str__(self):
        return f"{self.day_of_week}, {self.human_friendly_local} (local timezone: {self.local_time_zone})"

    def __repr__(self):
        self.__str__()

    def field_description_dict(self) -> dict:
        """
        Prints the description of all fields of this object in a dictionary {field_name: field_description}
        """
        output = {"class_name": f"{self.__class__.__name__})"}
        for field_name, field in self.model_fields.items():
            output[field_name] = field.description
        return output

    def to_descriptive_dict(self) -> dict:
        """
        Prints as a JSON and includes a description of all fields of this object
        """
        descriptive_dict = {}
        descriptive_dict.update(self.model_dump())
        descriptive_dict["_field_descriptions"] = self.field_description_dict()
        return descriptive_dict


if __name__ == "__main__":
    from pprint import pprint as print

    print("Printing `Timestamp.now()` object:")
    print(FullTimestamp.now().model_dump(), indent=4)

    print(
        "Printing `Timestamp.from_mapping(perf_counter_to_unix_mapping=(time.perf_counter_ns(), time.time_ns()))`:"
    )
    print(
        FullTimestamp.from_timebase_mapping(
            TimeBaseMapping(
                perf_counter_ns=time.perf_counter_ns(),
                utc_ns=time.time_ns()
            )
        ).model_dump(),
        indent=4,
    )

    print("Printing `Timestamp.now().to_descriptive_dict()`:")
    print(FullTimestamp.now().to_descriptive_dict(), indent=4)


