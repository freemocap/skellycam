from typing import List, Any, Dict

import numpy as np


def array_split_by(some_array: List, split_by: int):
    """
    Take an array, and split into subarrays by a factor.
    :param some_array:
    :param split_by:
    :return:
    """
    if len(some_array) == 1:
        return [some_array]

    as_nparray = np.array(some_array)
    splitted_arrays = np.array_split(as_nparray, split_by)
    # convert back to lists.
    return [subarray.tolist() for subarray in splitted_arrays]


def dict_split_by(some_dict: Dict[Any,Any], split_by:int):
    """
    Take a dictionary, and split into subdictionaries by a factor.
    :param some_dict:
    :param split_by:
    :return:
    """
    if len(some_dict) == 1:
        return [some_dict]

    as_nparray = np.array(list(some_dict.keys()))
    splitted_arrays = np.array_split(as_nparray, split_by)
    # convert back to lists.
    return [{key: some_dict[key] for key in subarray.tolist()} for subarray in splitted_arrays]