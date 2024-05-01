from typing import Tuple

import msgpack
import numpy as np
from pydantic import BaseModel, Field

from skellycam.backend.core.device_detection.camera_id import CameraId


class FramePayload(BaseModel):
    success: bool = Field(
        description="The `success` part of `success, image = cv2.VideoCapture.read()`"
    )
    image_data: bytes = Field(
        description="The raw image from `cv2.VideoCapture.read() as bytes`"
    )
    image_shape: Tuple[int, int, int] = Field("The shape of the image as a tuple of `(height, width, channels)`")

    timestamp_ns: int = Field(
        description="The timestamp of the frame in nanoseconds from `time.perf_counter_ns()`"
    )
    frame_number: int = Field(
        description="The frame number of the frame (`0` is the first frame pulled from this camera)"
    )
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from e.g. `0` for `cv2.VideoCapture(0)`"
    )

    @classmethod
    def create(cls,
               success: bool,
               image: np.ndarray,
               timestamp_ns: int,
               frame_number: int,
               camera_id: CameraId):
        return cls(
            success=success,
            image_data=image.tobytes(),
            image_shape=image.shape,
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id
        )

    @property
    def image(self) -> np.ndarray:
        return np.frombuffer(self.image_data, dtype=np.uint8).reshape(self.image_shape)

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self.dict(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        return cls(**msgpack.unpackb(msgpack_bytes, raw=False, use_list=False))