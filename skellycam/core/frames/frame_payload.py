import logging
import pickle
import time
from typing import Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field, field_validator

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId

logger = logging.getLogger(__name__)

FRAME_NUMBER_BYTES_LENGTH = 4


def int_to_fixed_bytes(value: int, length: int = FRAME_NUMBER_BYTES_LENGTH) -> bytes:
    return value.to_bytes(length, byteorder='big')


def fixed_bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, byteorder='big')


class FramePayload(BaseModel):
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from e.g. `0` for `cv2.VideoCapture(0)`")

    frame_number_bytes: bytes = Field(
        description="The number of frames read from the camera since the camera was started, "
                    "as a fixed-size byte array so the size in memory is always the same")

    bytes_per_pixel: int = Field(default=BYTES_PER_PIXEL, description="The number of bytes per pixel in the image")

    success: Optional[bool] = Field(default=None,
                                    description="The `success` part of `success, image = cv2.VideoCapture.read()`")
    image_data: Optional[bytes] = Field(default=None,
                                        description="The raw image from `cv2.VideoCapture.read() as bytes")
    image_shape: Optional[tuple] = Field(default=None,
                                         description="The shape of the image as a tuple of `(height, width)`")
    color_channels: Optional[int] = Field(default=None,
                                          description="Number of color channels, 3 for RGB, 1 for monochrome")
    timestamp_ns: Optional[int] = Field(default=None,
                                        description="The time the frame was read from the camera in nanoseconds")
    previous_frame_timestamp_ns: int = Field(default=None,
                                             description="Timestamp of the previous frame in nanoseconds (denotes object creation time for the first frame)")

    @property
    def frame_number(self) -> int:
        return fixed_bytes_to_int(self.frame_number_bytes)

    @frame_number.setter
    def frame_number(self, value: int):
        self.frame_number_bytes = int_to_fixed_bytes(value)

    @field_validator("frame_number_bytes", mode="before")
    @classmethod
    def frame_number_int_to_bytes(cls, v: int) -> bytes:
        if isinstance(v, int):
            return int_to_fixed_bytes(v)
        elif isinstance(v, bytes):
            return v
        else:
            raise ValueError(f"Frame number must be an int or bytes, not {type(v)}")

    @classmethod
    def from_previous(cls, previous: 'FramePayload') -> 'FramePayload':
        return cls(camera_id=previous.camera_id,
                   image_shape=previous.image_shape,
                   frame_number_bytes=int_to_fixed_bytes(previous.frame_number + 1),
                   previous_frame_timestamp_ns=previous.timestamp_ns)

    @classmethod
    def create_initial_frame(cls,
                             camera_id: CameraId,
                             image_shape: Tuple[int, ...],
                             ) -> 'FramePayload':
        image_shape, color_channels = cls._get_color_channels(image_shape)

        return cls(
            camera_id=camera_id,
            image_shape=image_shape,
            frame_number_bytes=int_to_fixed_bytes(0),
            color_channels=color_channels,
            previous_frame_timestamp_ns=time.perf_counter_ns(),
        )

    @classmethod
    def create_unhydrated_dummy(cls,
                                camera_id: CameraId,
                                image: np.ndarray,
                                ) -> 'FramePayload':
        image_shape, color_channels = cls._get_color_channels(image_shape=image.shape)
        instance = cls.create_initial_frame(camera_id=camera_id,
                                            image_shape=image_shape)

        instance.previous_frame_timestamp_ns = time.perf_counter_ns()
        instance.timestamp_ns = time.perf_counter_ns()
        return instance

    def to_buffer(self, image: np.ndarray) -> bytes:
        if self.hydrated:
            raise ValueError(
                "This method takes in the image separately here so we can avoid an unnecessary `copy` operation")
        image_bytes = image.tobytes()
        bytes_payload = self.to_unhydrated_bytes()
        # bufffer should be [`image_bytes` + `unhydrated_bytes`]
        return image_bytes + bytes_payload

    def to_unhydrated_bytes(self) -> bytes:
        without_image_data = self.model_dump(exclude={"image_data"})
        bytes_payload = pickle.dumps(without_image_data)
        return bytes_payload

    @classmethod
    def from_buffer(cls,
                    buffer: memoryview,
                    image_shape: Tuple[int, ...],
                    ) -> Tuple[bytes, bytes]:

        image_size = np.prod(image_shape) * BYTES_PER_PIXEL

        # buffer should be [`image_bytes` + `unhydrated_bytes`]
        image_buffer = buffer[:image_size]
        unhydrated_buffer = buffer[image_size:]

        instance = pickle.loads(unhydrated_buffer)
        image  = instance.image_from_bytes(image_buffer)
        instance.image = image
        return instance

    def image_from_bytes(self, image_bytes: bytes):
        image = np.frombuffer(image_bytes, dtype=np.uint8).reshape(self.image_shape)
        self._validate_image(image)
        return image

    @property
    def hydrated(self) -> bool:
        return self.image_data is not None

    @property
    def image(self) -> np.ndarray:
        return np.frombuffer(self.image_data, dtype=np.uint8).reshape(self.image_shape)

    @image.setter
    def image(self, image: np.ndarray):
        self.image_data = image.tobytes()
        self.image_shape = image.shape

    @property
    def height(self) -> int:
        return self.image_shape[0]

    @property
    def width(self) -> int:
        return self.image_shape[1]

    @property
    def resolution(self) -> tuple:
        return self.height, self.width

    @property
    def payload_size_in_kilobytes(self) -> float:
        return len(pickle.dumps(self.dict)) / 1024

    @property
    def time_since_last_frame_ns(self) -> float:
        return self.timestamp_ns - self.previous_frame_timestamp_ns

    def _validate_image(self, image: np.ndarray):
        if self.image_shape != image.shape:
            raise ValueError(f"Image shape mismatch - "
                             f"Expected: {self.image_shape}, "
                             f"Actual: {image.shape}")

    @staticmethod
    def calculate_image_checksum(image: np.ndarray) -> int:
        return int(np.sum(image))

    @staticmethod
    def calculate_pickle_checksum(pickle_bytes: bytes) -> int:
        return np.sum(np.frombuffer(pickle_bytes, dtype=np.uint8))

    @classmethod
    def _get_color_channels(cls,
                            image_shape: Tuple[int, ...]) -> Tuple[Tuple[int, ...], int]:
        if len(image_shape) == 2:
            color_channels = 1
        elif image_shape[-1] == 1:
            color_channels = 1
            image_shape = image_shape[:-1]
        elif len(image_shape) == 3:
            color_channels = image_shape[-1]
        else:
            raise ValueError(f"Image is the wrong shape - {image_shape}")
        return image_shape, color_channels

    def __eq__(self, other: 'FramePayload') -> bool:
        return self.model_dump() == other.model_dump()

    def __str__(self):
        print_str = (f"Camera{self.camera_id}:"
                     f"\n\tFrame#{self.frame_number} - [height: {self.height}, width: {self.width}, color channels: {self.color_channels}]"
                     f"\n\tPayload Size: {self.payload_size_in_kilobytes:.3f} KB (Hydrated: {self.image_data is not None}),"
                     f"\n\tSince Previous: {self.time_since_last_frame_ns / 1e6:.3f}ms")
        return print_str
