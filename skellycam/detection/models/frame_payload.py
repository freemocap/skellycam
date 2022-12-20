import dataclasses
from typing import NamedTuple

import numpy as np


@dataclasses.dataclass()
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    frame_number: int = None
    camera_id: str = None
