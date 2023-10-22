import calendar
from datetime import datetime, timezone
from typing import Optional

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


    @classmethod
    def from_utc_ns(cls, unix_timestamp_utc_ns: int):
        return cls.from_datetime(datetime.utcfromtimestamp(unix_timestamp_utc_ns / 1e9))

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

    def __repr__(self):
        self.__str__()



if __name__ == "__main__":
    from pprint import pprint as print

    print("Printing `Timestamp.now()` object:")
    print(Timestamp.now().dict(), indent=4)
    print("Printing `Timestamp.from_datetime(datetime.now())`:")
    print(Timestamp.from_datetime(datetime.now()).dict(), indent=4)
