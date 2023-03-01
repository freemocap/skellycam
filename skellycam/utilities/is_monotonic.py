import numpy as np


def is_monotonic(x):
    return np.all(np.diff(x) >= 0)
