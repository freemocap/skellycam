import pickle
import time
from typing import Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId


# from skellycam.core.frames.frame_lifecycle_timestamps import FrameLifeCycleTimestamps


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
                                         description="The shape of the image as a tuple of `(height, width, channels)`")

    timestamp_ns: Optional[int] = Field(default=None,
                                        description="The time the frame was read from the camera in nanoseconds")
    previous_frame_timestamp_ns: int = Field(default_factory=lambda: time.perf_counter_ns(),
                                             description="Timestamp of the previous frame in nanoseconds (dummy value on frame 0)")

    # timestamps: FrameLifeCycleTimestamps = Field(
    #     default_factory=FrameLifeCycleTimestamps,
    #     description="Record `time.perf_counter_ns()` at various points in the frame lifecycle")

    @classmethod
    def create_empty(cls,
                     camera_id: CameraId,
                     frame_number: int) -> 'FramePayload':
        return cls(
            camera_id=camera_id,
            frame_number=frame_number,
        )

    @classmethod
    def create_dummy(cls,
                     image: np.ndarray) -> 'FramePayload':
        return cls(
            camera_id=CameraId(0),
            success=True,
            image_data=image.tobytes() if image is not None else None,
            timestamp_ns=time.perf_counter_ns(),
            shared_memory_index=int(0),
            image_checksum=cls.calculate_checksum(image) if image is not None else None,
            image_shape=image.shape,
            frame_number=0,
        )

    def to_unhydrated_bytes(self) -> bytes:
        without_image_data = self.dict(exclude={"image_data"})
        # self.timestamps.pre_pickle = time.perf_counter_ns()
        bytes_payload = pickle.dumps(without_image_data)
        # self.timestamps.post_pickle = time.perf_counter_ns()
        return bytes_payload

    @classmethod
    def from_buffer(cls,
                    buffer: memoryview,
                    image_shape: Tuple[int, int, int],
                    ) -> 'FramePayload':
        if not len(image_shape) == 3:
            raise ValueError(
                f"Expected image shape to be a tuple of 3 integers (height, width, colors), got {image_shape}")
        # TODO - don't use global for BYTES_PER_PIXEL here should be able to use the `cls`
        image_size = np.prod(image_shape) * BYTES_PER_PIXEL
        image_memoryview = buffer[:image_size]

        unhydrated_data = buffer[image_size:]
        unhydrated_frame = pickle.loads(unhydrated_data)
        instance = cls(
            **unhydrated_frame,
        )
        instance.timestamps.post_create_frame_from_buffer = time.perf_counter_ns()
        image = np.ndarray(image_shape, dtype=np.uint8, buffer=image_memoryview)
        instance.timestamps.post_copy_image_from_buffer = time.perf_counter_ns()
        instance.image = image
        instance._validate_image(image=instance.image)
        instance.timestamps.done_create_from_buffer = time.perf_counter_ns()
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
        # self.timestamps.post_set_image_in_frame = time.perf_counter_ns()

    @property
    def height(self) -> int:
        return self.image_shape[0]

    @property
    def width(self) -> int:
        return self.image_shape[1]

    @property
    def color_channels(self) -> int:
        return self.image_shape[2]

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
    def calculate_checksum(image: np.ndarray) -> int:
        return int(np.sum(image))

    def __str__(self):
        print_str = (f"Camera{self.camera_id}:"
                     f"\n\tFrame#{self.frame_number} - [height: {self.height}, width: {self.width}, color channels: {self.image_shape[2]}]"
                     f"\n\tPayload Size: {self.payload_size_in_kilobytes:.3f} KB (Hydrated: {self.image_data is not None}),"
                     f"\n\tSince Previous: {self.time_since_last_frame_ns / 1e6:.3f}ms")
        return print_str


if __name__ == "__main__":

    camera_id = CameraId(0)
    image_shape_outer = (1080, 1920, 3)
    image_dtype = np.uint8
    frame_number_outer = 0
    previous_frame_timestamp_ns = time.perf_counter_ns()
    timestamp_ns = time.perf_counter_ns()

    tik = time.perf_counter_ns()
    test_image = np.random.randint(0, 255, size=image_shape_outer, dtype=image_dtype)
    read_duration_ns = time.perf_counter_ns() - tik  # secretly timing the time it takes to generate a random image

    frame = FramePayload(
        camera_id=camera_id,
        success=True,
        image_data=test_image.tobytes(),
        image_checksum=np.sum(test_image),
        image_shape=test_image.shape,
        timestamp_ns=timestamp_ns,
        frame_number=frame_number_outer,
        time_since_last_frame_ns=timestamp_ns - previous_frame_timestamp_ns,
        read_duration_ns=read_duration_ns,
    )

    print(f"HYDRATED FRAME PAYLOAD:\n{frame}\n--\n")

    tik = time.perf_counter_ns()
    unhydrated_bytes = frame.to_unhydrated_bytes()
    unhydrated_frame = pickle.loads(unhydrated_bytes)
    read_duration_ns = time.perf_counter_ns() - tik  # secretly timing the image-dehydration duration

    unhydrated_frame = FramePayload(
        **unhydrated_frame,
    )

    print(f"UNHYDRATED FRAME PAYLOAD:\n{unhydrated_frame}\n--\n")

    buffer = memoryview(frame.to_unhydrated_bytes() + test_image.tobytes())
    print(f"BUFFER SIZE: {len(buffer) / 1024:.2f} KB")
    frame_from_buffer = FramePayload.from_buffer(buffer=buffer,
                                                 image_shape=image_shape_outer)
    print(f"FRAME FROM BUFFER:\n{frame_from_buffer}\n--\n")

    bad_buffer = bytearray(buffer)  # Lookit this utter embarrassment of a buffer
    bad_buffer[0] = bad_buffer[0] + 1  # Terrible
    bad_buffer = memoryview(bad_buffer)  # Utter disgrace
    try:
        frame_from_bad_buffer = FramePayload.from_buffer(buffer=bad_buffer,
                                                         image_shape=image_shape_outer)
    except ValueError as e:
        print(f"ERROR: {type(e).__name__} - {e}")
        print(f"FRAME FROM BAD BUFFER FAILED SUCCESSFULLY")
