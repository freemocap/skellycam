import numpy as np
import numpy.typing as npt
from tzlocal import get_localzone

def ns_to_ms(ns: int | float | npt.NDArray) -> float | npt.NDArray:
    """
    Convert nanoseconds to milliseconds.
    """
    return ns / 1e6

def ms_to_ns(ms: float | npt.NDArray) -> int | npt.NDArray:
    """
    Convert milliseconds to nanoseconds.
    """
    return ms * 1e6  # type: ignore[return-value]

def ns_to_sec(ns: int | float | npt.NDArray) -> float | npt.NDArray:
    """
    Convert nanoseconds to seconds.
    """
    return ns / 1e9

def ms_to_sec(ms: float | npt.NDArray) -> float | npt.NDArray:
    """
    Convert milliseconds to seconds.
    """
    return ms / 1000.0
LOCAL_TIMEZONE = get_localzone()
