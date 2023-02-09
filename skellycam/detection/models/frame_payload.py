import dataclasses
from copy import copy

import numpy as np


@dataclasses.dataclass()
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    image_shape: tuple = None
    timestamp_ns: float = None
    number_of_frames_received: int = None  # how many frames have been grabbed from this camera?
    number_of_frames_recorded: int = None  # how many frames have been recorded (to be dumped to video)?
    camera_id: str = None
    mean_frames_per_second: float = None
    queue_size: int = None


