import logging
from datetime import datetime


class CustomFormatter(logging.Formatter):
    """A custom Formatter class to include microseconds in log timestamps."""

    def formatTime(self, record, datefmt=None):
        created = record.created
        if isinstance(created, float) or isinstance(created, int):
            timestamp = created
        else:
            raise TypeError("Invalid type for 'created'")

        date_format_with_microseconds = (
            "%Y-%m-%dT%H:%M:%S.%f"  # Including microseconds with %f
        )
        return datetime.strftime(
            datetime.fromtimestamp(timestamp), date_format_with_microseconds
        )
