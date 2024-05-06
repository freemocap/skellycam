from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.detection.camera_id import CameraId


class FramePayload(BaseModel):
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from e.g. `0` for `cv2.VideoCapture(0)`")
    success: bool = Field(description="The `success` part of `success, image = cv2.VideoCapture.read()`")
    image_data: Optional[bytes] = Field(description="The raw image from `cv2.VideoCapture.read() as bytes`")
    image_shape: tuple = Field("The shape of the image as a tuple of `(height, width, channels)`")
    timestamp_ns: int = Field(description="The timestamp of the frame in nanoseconds from `time.perf_counter_ns()`")
    frame_number: int = Field(
        description="The frame number of the frame (`0` is the first frame pulled from this camera)")
    read_duration_ns: int = Field("The amount of time that elapsed while reading the frame in nanoseconds")

    @classmethod
    def create(cls,
               success: bool,
               image: np.ndarray,
               timestamp_ns: int,
               frame_number: int,
               camera_id: CameraId,
               read_duration_ns: int, ):
        return cls(
            success=success,
            image_data=image.tobytes(),
            image_shape=image.shape,
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id,
            read_duration_ns=read_duration_ns,
        )

    @property
    def image(self) -> np.ndarray:
        return np.frombuffer(self.image_data, dtype=np.uint8).reshape(self.image_shape)

    @image.setter
    def image(self, image: np.ndarray):
        self.image_data = image.tobytes()
        self.image_shape = image.shape

    @property
    def width(self) -> int:
        return self.image_shape[1]

    @property
    def height(self) -> int:
        return self.image_shape[0]

    @property
    def resolution(self) -> tuple:
        return self.width, self.height

    @property
    def size_in_kilobytes(self) -> float:
        return len(self.image_data) / 1024