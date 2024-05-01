import numpy as np
from pydantic import BaseModel, Field

from skellycam.backend.core.device_detection.camera_id import CameraId

class FramePayload(BaseModel):
    success: bool = Field(
        description="The `success` part of `success, image = cv2.VideoCapture.read()`"
    )
    image: np.ndarray = Field(
        description="The raw image from `cv2.VideoCapture.read() as a numpy array`"
    )
    timestamp_ns: int = Field(
        description="The timestamp of the frame in nanoseconds,"
        " from `time.perf_counter_ns()`"
    )
    frame_number: int = Field(
        description="The frame number of the frame "
        "(`0` is the first frame pulled from this camera)"
    )
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from,"
        " e.g. `0` if this is the `cap = cv2.VideoCapture(0)` camera"
    )

