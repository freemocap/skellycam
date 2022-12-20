from typing import List

import numpy as np


def array_split_by(some_array: List, split_by: int):
    """
    Take an array, and split into subarrays by a factor.
    :param some_array:
    :param split_by:
    :return:
    """
    as_nparray = np.array(some_array)
    splitted_arrays = np.array_split(as_nparray, split_by)
    # convert back to lists.
    return [subarray.tolist() for subarray in splitted_arrays]
