from dataclasses import dataclass

import numpy as np


@dataclass
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    camera_id: str = None
    number_of_frames_received: int = None
    compression: str = None
