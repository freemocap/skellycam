import numpy as np
import numpy.typing as npt
from tzlocal import get_localzone

def ns_to_ms(ns: int | float | npt.NDArray) -> float | npt.NDArray:
    """
    Convert nanoseconds to milliseconds.
    """
    return ns / 1e6

def ms_to_ns(ms: int | float | np.integer | np.floating | npt.NDArray) -> int | npt.NDArray:
    """Convert to signed 64-bit nanoseconds, rounding nearest with ties to even.

    Scalars return Python ints; arrays retain their shape and return int64.
    Reject nonfinite inputs and overflow instead of silently wrapping timestamps.
    """
    limit_ms = (2 ** 63 - 1) // 1_000_000
    if isinstance(ms, (int, np.integer)) and not isinstance(ms, bool):
        if not -limit_ms <= int(ms) <= limit_ms:
            raise OverflowError('Nanoseconds exceed the signed 64-bit range')
        return int(ms) * 1_000_000
    values = np.asarray(ms)
    if values.dtype.kind not in 'iuf':
        raise TypeError('Milliseconds must contain real numbers')
    if not np.all(np.isfinite(values)):
        raise ValueError('Milliseconds must be finite')
    if values.dtype.kind in 'iu':
        if np.any(values < -limit_ms) or np.any(values > limit_ms):
            raise OverflowError('Nanoseconds exceed the signed 64-bit range')
        result = np.asarray(values.astype(np.int64) * 1_000_000, dtype=np.int64)
    else:
        with np.errstate(over='ignore'):
            rounded = np.rint(values.astype(np.float64) * 1_000_000)
        if np.any(rounded < -(2 ** 63)) or np.any(rounded >= 2 ** 63):
            raise OverflowError('Nanoseconds exceed the signed 64-bit range')
        result = np.asarray(rounded, dtype=np.int64)
    return result if isinstance(ms, np.ndarray) else int(result)


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
