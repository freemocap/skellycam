from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.detection.camera_id import CameraId
from skellycam.core.frames.shared_image_memory import SharedPayloadMemoryManager


class FramePayload(BaseModel):
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from e.g. `0` for `cv2.VideoCapture(0)`")
    success: bool = Field(description="The `success` part of `success, image = cv2.VideoCapture.read()`")
    image_data: Optional[bytes] = Field(default=None,
                                        description="The raw image from `cv2.VideoCapture.read() as bytes")
    shared_memory_index: Optional[int] = Field(description="The index in the shared memory manager for this image")
    image_checksum: Optional[int] = Field(description="The sum of the pixel values of the image, to verify integrity")
    image_shape: tuple = Field("The shape of the image as a tuple of `(height, width, channels)`")
    timestamp_ns: int = Field(description="The timestamp of the frame in nanoseconds from `time.perf_counter_ns()`")
    frame_number: int = Field(
        description="The frame number of the frame (`0` is the first frame pulled from this camera)")
    time_since_last_frame_ns: int = Field(
        description="The amount of time that elapsed since the last frame in nanoseconds (0 for the first frame)")
    read_duration_ns: int = Field("The amount of time that elapsed while reading the frame in nanoseconds")

    @classmethod
    def as_shared_memory(cls,
                         shared_memory_manager: SharedPayloadMemoryManager,
                         success: bool,
                         image: np.ndarray,
                         timestamp_ns: int,
                         frame_number: int,
                         camera_id: CameraId,
                         read_duration_ns: int,
                         time_since_last_frame_ns: int,
                         ) -> 'FramePayload':
        return cls(
            success=success,
            shared_memory_index=shared_memory_manager.put_image(image=image,
                                                                camera_id=camera_id),
            image_shape=image.shape,
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id,
            read_duration_ns=read_duration_ns,
            image_checksum=np.sum(image),
            time_since_last_frame_ns=time_since_last_frame_ns,
        )

    def hydrate_shared_memory_image(self,
                                    shared_memory_manager: SharedPayloadMemoryManager):
        image = shared_memory_manager.get_image(index=self.shared_memory_index,
                                                camera_id=self.camera_id)
        if not np.sum(image) == self.image_checksum:
            raise ValueError(f"Image checksum does not match for {self.camera_id}")
        self.image_data = image.tobytes()

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

    def _validate_image(self, image: np.ndarray):
        if self.image_shape != image.shape:
            raise ValueError(f"Image shape mismatch - "
                             f"Expected: {self.image_shape}, "
                             f"Actual: {image.shape}")
        if self.image_dtype != image.dtype:
            raise ValueError(f"Image dtype mismatch - "
                             f"Expected: {self.image_dtype}, "
                             f"Actual: {image.dtype}")
        check_sum = np.sum(image)
        if self.image_checksum != check_sum:
            raise ValueError(f"Image checksum mismatch - "
                             f"Expected: {self.image_checksum}, "
                             f"Actual: {check_sum}")

    def __str__(self):
        print_str = f"Camera{self.camera_id}: Frame-{self.frame_number}, " \
                    f"[w:{self.width}, h:{self.height}], " \
                    f"Hydrated: {self.image is not None}, " \
                    f"Payload Size: {self.size_in_kilobytes:.2f} KB - " \
                    f"Since previous: {self.time_since_last_frame_ns / 1e6:.6f}ms"
        return print_str
