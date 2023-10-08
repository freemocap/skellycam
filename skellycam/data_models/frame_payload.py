from ctypes import c_wchar_p
import logging
from ctypes import c_wchar_p
from dataclasses import dataclass
from multiprocessing import Value
from multiprocessing.shared_memory import SharedMemory

import numpy as np





@dataclass
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    camera_id: str = None
    number_of_frames_received: int = None
    compression: str = None
