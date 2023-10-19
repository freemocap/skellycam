import numpy as np
from pydantic import BaseModel

from skellycam.models.cameras.camera_id import CameraId


class FramePayload(BaseModel):
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    number_of_frames_received: int = None  # how many frames have been grabbed from this camera?
    camera_id: CameraId = None
