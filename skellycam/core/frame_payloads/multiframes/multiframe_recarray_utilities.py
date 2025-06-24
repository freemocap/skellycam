import numpy as np


def mf_recarray_find_earliest_timestamps(mf: np.recarray) -> int:
    """
    Find the earliest timestamp in a multiframe record array.

    Args:
        mf (np.recarray): The multiframe record array.

    Returns:
        int: The earliest timestamp in nanoseconds.
    """
    if mf.size == 0:
        raise ValueError("The multiframe record array is empty.")
    ts = []
    for name in mf.dtype.names:
        ts.append(mf[name].frame_metadata.timestamps.pre_frame_grab_ns[0])
    if len(ts) == 0:
        raise ValueError("No timestamps found in the multiframe record array.")
    return int(np.min(ts))

def mf_recarray_find_multiframe_number(mf: np.recarray) -> int:
    if mf.size == 0:
        raise ValueError("The multiframe record array is empty.")
    frame_numbers = []
    for name in mf.dtype.names:
        frame_numbers.append(mf[name].frame_metadata.frame_number[0])
    if len(frame_numbers) == 0:
        raise ValueError("No timestamps found in the multiframe record array.")
    if len(set(frame_numbers)) > 1:
        raise ValueError("Multiframe record array contains multiple frame numbers.")
    return int(frame_numbers[0])