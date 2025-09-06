from tzlocal import get_localzone

def ns_to_ms(ns: int|float) -> float:
    """
    Convert nanoseconds to milliseconds.
    """
    return ns / 1e6

def ms_to_ns(ms: float) -> int:
    """
    Convert milliseconds to nanoseconds.
    """
    return int(ms * 1e6)

def ns_to_sec(ns: int|float) -> float:
    """
    Convert nanoseconds to seconds.
    """
    return ns / 1e9

def ms_to_sec(ms: float) -> float:
    """
    Convert milliseconds to seconds.
    """
    return ms / 1000.0
LOCAL_TIMEZONE = get_localzone()