import pickle
from typing import Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.detection.camera_id import CameraId

BYTES_PER_PIXEL = 1


class FramePayload(BaseModel):
    camera_id: CameraId = Field(
        description="The camera ID of the camera that this frame came from e.g. `0` for `cv2.VideoCapture(0)`")
    success: bool = Field(description="The `success` part of `success, image = cv2.VideoCapture.read()`")
    image_data: Optional[bytes] = Field(default=None,
                                        description="The raw image from `cv2.VideoCapture.read() as bytes")
    image_checksum: int = Field(description="The sum of the pixel values of the image, to verify integrity")
    image_shape: tuple = Field("The shape of the image as a tuple of `(height, width, channels)`")
    bytes_per_pixel: int = Field(default=BYTES_PER_PIXEL, description="The number of bytes per pixel in the image")
    timestamp_ns: int = Field(description="The timestamp of the frame in nanoseconds from `time.perf_counter_ns()`")
    read_duration_ns: int = Field(description="The time taken to read the frame in nanoseconds")
    frame_number: int = Field(description="The number of frames read from the camera since the camera was started")
    time_since_last_frame_ns: int = Field(description="The time since the previous frame in nanoseconds")

    @classmethod
    def create_dummy(cls, image: np.ndarray) -> 'FramePayload':

        return cls(
            camera_id=CameraId(0),
            success=True,
            image_data=image.tobytes() if image is not None else None,
            shared_memory_index=int(0),
            image_checksum=np.sum(image),
            image_shape=image.shape,
            timestamp_ns=0,
            frame_number=0,
            time_since_last_frame_ns=0,
            read_duration_ns=0,
        )

    def to_unhydrated_bytes(self) -> bytes:
        without_image_data = self.dict(exclude={"image_data"})
        return pickle.dumps(without_image_data)

    def to_buffer(self) -> bytes:
        image_buffer = self.image_data
        return image_buffer + self.to_unhydrated_bytes()

    @classmethod
    def from_buffer(cls,
                    buffer: bytes,
                    image_shape: Tuple[int, int, int],
                    ) -> 'FramePayload':
        if not len(image_shape) == 3:
            raise ValueError(
                f"Expected image shape to be a tuple of 3 integers (height, width, colors), got {image_shape}")
        image_size = np.prod(
            image_shape) * BYTES_PER_PIXEL  # TODO - don't use global here should be able to use the `cls`
        image_data = buffer[:image_size]
        unhydrated_data = buffer[image_size:]
        unhydrated_frame = pickle.loads(unhydrated_data)
        instance = cls(
            **unhydrated_frame,
            image_data=image_data,
        )
        instance._validate_image(image=instance.image)
        return instance

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
    def color_channels(self) -> int:
        return self.image_shape[2]

    @property
    def resolution(self) -> tuple:
        return self.width, self.height

    @property
    def size_in_kilobytes(self) -> float:
        return len(pickle.dumps(self.dict)) / 1024

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

    def __str__(self):
        print_str = (f"Camera{self.camera_id}:"
                     f"\n\tFrame#{self.frame_number} - [height: {self.height}, width: {self.width}, color channels: {self.image_shape[2]}]"
                     f"\n\tHydrated: {self.image_data is not None}, "
                     f"\n\tPayload Size: {self.size_in_kilobytes:.2f} KB "
                     f"\n\tSince previous: {self.time_since_last_frame_ns / 1e6:.6f}ms")
        return print_str


if __name__ == "__main__":
    import time

    camera_id = CameraId(0)
    image_shape = (1080, 1920, 3)
    image_dtype = np.uint8
    frame_number = 0
    previous_frame_timestamp_ns = time.perf_counter_ns()
    timestamp_ns = time.perf_counter_ns()

    tik = time.perf_counter_ns()
    test_image = np.random.randint(0, 255, size=image_shape, dtype=image_dtype)
    read_duration_ns = time.perf_counter_ns() - tik  # secretly timing the time it takes to generate a random image

    frame = FramePayload(
        camera_id=camera_id,
        success=True,
        image_data=test_image.tobytes(),
        image_checksum=np.sum(test_image),
        image_shape=test_image.shape,
        timestamp_ns=timestamp_ns,
        frame_number=frame_number,
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
    unhydrated_frame.read_duration_ns = read_duration_ns

    print(f"UNHYDRATED FRAME PAYLOAD:\n{unhydrated_frame}\n--\n")

    buffer = frame.to_buffer()
    print(f"BUFFER SIZE: {len(buffer) / 1024:.2f} KB")
    frame_from_buffer = FramePayload.from_buffer(buffer=buffer,
                                                 image_shape=image_shape)
    print(f"FRAME FROM BUFFER:\n{frame_from_buffer}\n--\n")

    bad_buffer = bytearray(buffer)  # Lookit this utter embarrassment of a buffer
    bad_buffer[0] = bad_buffer[0] + 1  # Terrible
    bad_buffer = bytes(bad_buffer)  # Utter disgrace
    try:
        frame_from_bad_buffer = FramePayload.from_buffer(buffer=bad_buffer,
                                                         image_shape=image_shape)
    except ValueError as e:
        print(f"ERROR: {type(e).__name__} - {e}")
        print(f"FRAME FROM BAD BUFFER FAILED SUCCESSFULLY")
