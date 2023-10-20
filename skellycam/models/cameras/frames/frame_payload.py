import struct

import numpy as np
from PySide6.QtGui import QImage
from pydantic import BaseModel, Field


class RawImage(BaseModel):
    bytes: bytes
    width: int
    height: int
    channels: int
    data_type: str

    @property
    def image(self) -> np.ndarray:
        return np.frombuffer(self.bytes, dtype=self.data_type).reshape((self.height, self.width, self.channels))

    @classmethod
    def from_cv2_image(cls, image: np.ndarray):
        return cls(
            bytes=image.tobytes(),
            width=image.shape[1],
            height=image.shape[0],
            channels=image.shape[2],
            data_type=str(image.dtype),
        )

    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        header_size = struct.calcsize('4i')
        width, height, channels, data_type_length = struct.unpack('4i', byte_obj[:header_size])
        data_type_start = header_size
        data_type_end = data_type_start + data_type_length
        data_type = byte_obj[data_type_start:data_type_end].decode()
        image_bytes = byte_obj[data_type_end:]
        return cls(bytes=image_bytes,
                   width=width,
                   height=height,
                   channels=channels,
                   data_type=data_type)

    def to_bytes(self):
        header = struct.pack('4i', self.width, self.height, self.channels, len(self.data_type))
        return header + self.data_type.encode() + self.bytes

    def to_q_image(self) -> QImage:
        return QImage(self.bytes,
                      self.width,
                      self.height,
                      self.channels * self.width,
                      QImage.Format_RGB888)


class FramePayload(BaseModel):
    success: bool = Field(description="The `success` part of `success, image = cv2.VideoCapture.read()`")
    raw_image: RawImage = Field(description="The raw image from `cv2.VideoCapture.read()`")
    timestamp_ns: int = Field(description="The timestamp of the frame in nanoseconds,"
                                          " from `time.perf_counter_ns()`")
    frame_number: int = Field(description="The frame number of the frame "
                                          "(`0` is the first frame pulled from this camera)")
    camera_id: int = Field(description="The camera ID of the camera that this frame came from,"
                                       " e.g. `0` if this is the `cap = cv2.VideoCapture(0)` camera")

    @property
    def image(self) -> np.ndarray:
        return self.raw_image.image

    @classmethod
    def create(cls,
               success: bool,
               image: np.ndarray,
               timestamp_ns: int,
               frame_number: int,
               camera_id: int):
        return cls(
            success=success,
            raw_image=RawImage.from_cv2_image(image),
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id,
        )

    def to_bytes(self):
        header = struct.pack('bqiq', self.success, self.timestamp_ns, self.frame_number, self.camera_id)
        return header + self.raw_image.to_bytes()

    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        header_size = struct.calcsize('bqiq')
        success, timestamp_ns, frame_number, camera_id = struct.unpack('bqiq', byte_obj[:header_size])
        image = RawImage.from_bytes(byte_obj[header_size:])
        return cls(success=success,
                   timestamp_ns=timestamp_ns,
                   frame_number=frame_number,
                   camera_id=camera_id,
                   raw_image=image)

    def to_q_image(self) -> QImage:
        return self.raw_image.to_q_image()


if __name__ == "__main__":
    from skellycam.tests.test_frame_payload_to_and_from_bytes import test_frame_payload_to_and_from_bytes

    test_frame_payload_to_and_from_bytes()
