import dataclasses

import numpy as np


# TODO: This shouldn't be a dataclass. Use __slots__
# https://stackoverflow.com/questions/472000/usage-of-slots
@dataclasses.dataclass()
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    # using nanoseconds to avoid floating point inprecision -  divide by `1e9` to get seconds
    timestamp_ns: int = None
    camera_id: str = None
