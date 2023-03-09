import dataclasses

import numpy as np


# TODO: This shouldn't be a dataclass. Use __slots__
# https://stackoverflow.com/questions/472000/usage-of-slots
@dataclasses.dataclass()
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: int = None  # using nanoseconds to avoid floating point inprecision -  divide by `1e9` to get seconds
    camera_id: str = None
    # telemetry
    # TODO: Telemetry is not the job of the FramePayload to communicate
    #  The class itself can emit this data, and consumers can use it to do its job
    #  Why?
    #  The FramePayload represents a Frame. The goal is to communicate this frame as tightly, and as fast as possible
    #  Every single field in the FramePayload must be assessed Marie Kondo-style for the purposes of performance optimization
    #  of Frame transfer both across threads as well as across Processes.
    number_of_frames_received: int = None  # how many frames have been grabbed from this camera?
    number_of_frames_recorded: int = None  # how many frames have been recorded (i.e. #frames that will be in saved video))?
    current_chunk_size: int = None  # how many frames are in the current chunk (not yet saved to video file)?
