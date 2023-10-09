import calendar
from datetime import datetime, timezone
from typing import Optional, Union, Dict

from pydantic import BaseModel
from tzlocal import get_localzone


class Timestamp(BaseModel):
    """
    The world's most extravagant timestamp object

    If you manage to come up with a timestamp-related use case that isn't covered by this bad boi, let me know and we'll add it
    """
    unix_timestamp_utc: float
    unix_timestamp_local: float
    unix_timestamp_utc_isoformat: str
    unix_timestamp_local_isoformat: str
    perf_counter_ns: Optional[int]
    local_time_zone: str
    human_friendly_utc: str
    human_friendly_local: str
    day_of_week: str
    calendar_week: int
    day_of_year: int
    is_leap_year: bool

    # @classmethod
    # def from_perf_counter_and_offset(cls,
    #                                  perf_counter: Union[int, float],
    #                                  # a call from `time.perf_counter_ns():int` or `time.perf_counter():float`
    #                                  offset_mapping: Dict[int, Union[datetime, 'Timestamp']]
    #                                  # a dictionary mapping a perf_counter_ns or perf_counter to a datetime or Timestamp object
    #                                  ):
    #     """
    #     Create a timestamp object from a perf_counter_ns or perf_counter and an offset dictionary mapping an and initial perf_counter_ns or perf_counter to a datetime or Timestamp object
    #     """
    #     perf_counter_ns = cls._convert_perf_counter(perf_counter)
    #
    #     reference_perf_ns, reference_timestamp = cls._unpack_mapping(offset_mapping)
    #
    #     # calculate the offset
    #     offset_ns = perf_counter_ns - reference_perf_ns
    #
    #     # calculate the timestamp
    #     timestamp_ns = reference_timestamp.datetime + offset_ns



    @classmethod
    def _convert_perf_counter(cls, perf_counter: Union[int, float]):
        """
        If the perf_counter is a float (e.g. from time.perf_counter()), convert it to an int (e.g. time.perf_counter_ns())

        Perf_counter_ns is more precise because it avoids floating point error, but perf_counter is more human-readable, so we want to support both

        Converting a perf_counter to a perf_counter_ns is effectively enshrining floating point error, but like, whatever lol
        """

        if isinstance(perf_counter, float):
            perf_counter_ns = int(
                perf_counter * 1e9)  # convert to ns (by enshrining floating point error, but like, whatever)

    @classmethod
    def _unpack_reference_mapping(cls, offset_mapping: Dict[Union[int, float], Union[datetime, 'Timestamp']]):
        """
        Unpack the reference mapping into a perf_counter_ns and a timestamp
        convert
        """
        _perf_counter = list(offset_mapping.keys())[0]
        _timestamp = offset_mapping[_perf_counter]
        if isinstance(_timestamp, datetime):
            _timestamp = int(_timestamp.timestamp() * 1e9)
        return _perf_counter, _timestamp

    @classmethod
    def from_datetime(cls, datetime_reference: datetime):
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
        )

    @classmethod
    def now(cls):
        return cls.from_datetime(datetime.now())

    @property
    def utc(self) -> float:
        return self.unix_timestamp_utc

    def __str__(self):
        return f"{self.day_of_week}, {self.human_friendly_local} (local timezone: {self.local_time_zone})"



if __name__ == "__main__":
    from pprint import pprint as print

    print("Printing `Timestamp.now()` object:")
    print(Timestamp.now().dict(), indent=4)
    print("Printing `Timestamp.from_datetime(datetime.now())`:")
    print(Timestamp.from_datetime(datetime.now()).dict(), indent=4)
