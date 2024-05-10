# from skellycam.core.frames.frame_lifecycle_timestamps import FrameLifeCycleTimestamps
import logging
import pickle
import time
from typing import Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId

logger = logging.getLogger(__name__)


class FramePayload(BaseModel):
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from e.g. `0` for `cv2.VideoCapture(0)`")

    frame_number: int = Field(description="The number of frames read from the camera since the camera was started")

    bytes_per_pixel: int = Field(default=BYTES_PER_PIXEL, description="The number of bytes per pixel in the image")

    success: Optional[bool] = Field(default=None,
                                    description="The `success` part of `success, image = cv2.VideoCapture.read()`")
    image_data: Optional[bytes] = Field(default=None,
                                        description="The raw image from `cv2.VideoCapture.read() as bytes")
    image_checksum: Optional[int] = Field(default=None,
                                          description="The sum of the pixel values of the image, to verify integrity")
    image_shape: Optional[tuple] = Field(default=None,
                                         description="The shape of the image as a tuple of `(height, width)`")
    color_channels: Optional[int] = Field(default=None,
                                          description="Number of color channels, 3 for RGB, 1 for monochrome")
    timestamp_ns: Optional[int] = Field(default=None,
                                        description="The time the frame was read from the camera in nanoseconds")
    previous_frame_timestamp_ns: int = Field(default_factory=lambda: time.perf_counter_ns(),
                                             description="Timestamp of the previous frame in nanoseconds (dummy value on frame 0)")
    dummy: bool = Field(default=False, description="This is a dummy frame to be used to calculate the buffer size")

    # timestamps: FrameLifeCycleTimestamps = Field(
    #     default_factory=FrameLifeCycleTimestamps,
    #     description="Record `time.perf_counter_ns()` at various points in the frame lifecycle")

    @classmethod
    def create_empty(cls,
                     camera_id: CameraId,
                     image_shape: Tuple[int, ...],
                     frame_number: int) -> 'FramePayload':
        image_shape, color_channels = cls._get_color_channels(image_shape)

        return cls(
            camera_id=camera_id,
            image_shape=image_shape,
            frame_number=frame_number,
            color_channels=color_channels
        )

    @classmethod
    def _get_color_channels(cls,
                            image_shape:Tuple[int,...]) -> Tuple[Tuple[int,...], int]:
        if len(image_shape) == 2:
            color_channels = 1
        elif image_shape[-1] == 1:
            color_channels = 1
            del image_shape[-1]
        elif len(image_shape) == 3:
            color_channels = image_shape[-1]
        else:
            raise ValueError(f"Image is the wrong shape - {image_shape}")
        return image_shape, color_channels

    @classmethod
    def create_hydrated_dummy(cls,
                              image: np.ndarray,
                              ) -> 'FramePayload':
        instance = cls.create_empty(CameraId(0),
                                    image_shape=image.shape,
                                    frame_number=0)
        instance.image = image
        instance.previous_frame_timestamp_ns = time.perf_counter_ns()
        instance.timestamp_ns = time.perf_counter_ns()
        return instance

    @classmethod
    def create_unhydrated_dummy(cls,
                                camera_id: CameraId,
                                image: np.ndarray,
                                ) -> 'FramePayload':
        image_shape, color_channels = cls._get_color_channels(image_shape=image.shape)
        instance = cls.create_empty(camera_id=camera_id,
                                    image_shape=image_shape,
                                    frame_number=0)

        instance.image_checksum = cls.calculate_image_checksum(image)
        instance.previous_frame_timestamp_ns = time.perf_counter_ns()
        instance.timestamp_ns = time.perf_counter_ns()
        return instance

    def to_buffer(self, image: np.ndarray) -> memoryview:
        if self.hydrated:
            raise ValueError("This method takes in the image separately here so we can avoid an unnecessary `copy` operation")
        image_bytes = image.tobytes()
        bytes_payload = self.to_unhydrated_bytes()
        # bufffer should be [`image_bytes` + `unhydrated_bytes`]
        return memoryview(image_bytes + bytes_payload)

    def to_unhydrated_bytes(self) -> bytes:
        without_image_data = self.dict(exclude={"image_data"})
        # self.timestamps.pre_pickle = time.perf_counter_ns()
        bytes_payload = pickle.dumps(without_image_data)
        # self.timestamps.post_pickle = time.perf_counter_ns()
        if not self.dummy:
            logger.trace(
                f"Pickled frame payload to {len(bytes_payload)} bytes -"
                f"(checksum: {self.calculate_pickle_checksum(bytes_payload)})")
        return bytes_payload

    @classmethod
    def from_buffer(cls,
                    buffer: memoryview,
                    image_shape: Tuple[int, ...],
                    ) -> 'FramePayload':

        if len(image_shape) == 2:
            image_shape = (*image_shape, 1)

        image_size = np.prod(image_shape) * BYTES_PER_PIXEL

        # buffer should be [`image_bytes` + `unhydrated_bytes`]
        image_buffer = buffer[:image_size]
        unhydrated_buffer = buffer[image_size:]
        unhydrated_frame = pickle.loads(unhydrated_buffer)
        instance = cls(
            **unhydrated_frame
        )
        # instance.timestamps.pre_copy_image_from_buffer = time.perf_counter_ns()
        instance.image = np.ndarray(image_shape, dtype=np.uint8, buffer=image_buffer)
        # instance.timestamps.post_copy_image_from_buffer = time.perf_counter_ns()

        instance._validate_image(image=instance.image)
        # instance.timestamps.done_create_from_buffer = time.perf_counter_ns()
        return instance

    @property
    def hydrated(self) -> bool:
        return self.image_data is not None

    @property
    def image(self) -> np.ndarray:
        return np.frombuffer(self.image_data, dtype=np.uint8).reshape(self.image_shape)

    @image.setter
    def image(self, image: np.ndarray):
        # self.timestamps.pre_set_image_in_frame = time.perf_counter_ns()
        self.image_data = image.tobytes()
        self.image_shape = image.shape
        self.image_checksum = self.calculate_image_checksum(image)
        # self.timestamps.post_set_image_in_frame = time.perf_counter_ns()

    @property
    def height(self) -> int:
        return self.image_shape[0]

    @property
    def width(self) -> int:
        return self.image_shape[1]

    @property
    def resolution(self) -> tuple:
        return self.width, self.height

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
        check_sum = np.sum(image)
        if self.image_checksum != check_sum:
            raise ValueError(f"Image checksum mismatch - "
                             f"Expected: {self.image_checksum}, "
                             f"Actual: {check_sum}")

    @staticmethod
    def calculate_image_checksum(image: np.ndarray) -> int:
        return int(np.sum(image))

    @staticmethod
    def calculate_pickle_checksum(pickle_bytes: bytes) -> int:
        return np.sum(np.frombuffer(pickle_bytes, dtype=np.uint8))

    def __eq__(self, other: 'FramePayload') -> bool:
        return self.dict() == other.dict()

    def __str__(self):
        print_str = (f"Camera{self.camera_id}:"
                     f"\n\tFrame#{self.frame_number} - [height: {self.height}, width: {self.width}, color channels: {self.color_channels}]"
                     f"\n\tPayload Size: {self.payload_size_in_kilobytes:.3f} KB (Hydrated: {self.image_data is not None}),"
                     f"\n\tSince Previous: {self.time_since_last_frame_ns / 1e6:.3f}ms")
        return print_str
