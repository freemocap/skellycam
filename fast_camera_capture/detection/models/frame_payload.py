from typing import NamedTuple

import numpy as np


class FramePayload(NamedTuple):
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    frame_number: int = None
    webcam_id: str = None
