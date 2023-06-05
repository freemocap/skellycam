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


import numpy as np


class FramePayload:
    """
    A class used to represent a frame payload.

    Uses the __slots__ attribute to improve performance ( https://stackoverflow.com/questions/472000/usage-of-slots ).

    Attributes
    ----------
    success : bool
        A flag indicating success (default is False).
    image : np.ndarray
        A numpy array holding the image data. Shape will be [resolution_width, resolution_height, number_of_color_channels] Default color space is BGR, use `cv2.cvtColor(image, cv2.COLOR_BGR2RGB)` to get RBG. Default is None).
    timestamp_ns : int
        The timestamp in nanoseconds to avoid floating point imprecision.
         Divide by `1e9` to get seconds (default is None).
    camera_id : str
        The ID of the camera (default is None).

    """

    __slots__ = ['success', 'image', 'timestamp_ns', 'camera_id']

    def __init__(self, success: bool = False, image: np.ndarray = None, timestamp_ns: int = None,
                 camera_id: str = None):
        self.success = success
        self.image = image
        self.timestamp_ns = timestamp_ns
        self.camera_id = camera_id
