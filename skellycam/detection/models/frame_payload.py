import dataclasses

import numpy as np


@dataclasses.dataclass()
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: int = None  # using nanoseconds to avoid floating point inprecision -  divide by `1e9` to get seconds
    camera_id: str = None
    # telemetry
    number_of_frames_received: int = None  # how many frames have been grabbed from this camera?
    number_of_frames_recorded: int = None  # how many frames have been recorded (i.e. #frames that will be in saved video))?
    current_chunk_size: int = None  # how many frames are in the current chunk (not yet saved to video file)?
