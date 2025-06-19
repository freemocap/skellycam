from tzlocal import get_localzone

def ns_to_ms(ns: int) -> float:
    """
    Convert nanoseconds to milliseconds.
    """
    return ns / 1e6


def ns_to_sec(ns: int) -> float:
    """
    Convert nanoseconds to seconds.
    """
    return ns / 1e9

LOCAL_TIMEZONE = get_localzone()