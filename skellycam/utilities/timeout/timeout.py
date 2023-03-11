import traceback
from datetime import datetime


class Timeout:
    def __init__(self, timeout_in_seconds, error_message="Timeout achieved - Exiting"):
        self._timeout_in_seconds = timeout_in_seconds
        self._error_message = error_message
        self._start_time = datetime.now()

    def is_timed_out(self):
        delta = datetime.now() - self._start_time
        return delta.total_seconds() > self._timeout_in_seconds

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, tb)
            # return False # uncomment to pass exception through

        return True
