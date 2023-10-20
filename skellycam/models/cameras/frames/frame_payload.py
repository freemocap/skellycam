import itertools
import struct
from typing import Dict, Optional, List

import numpy as np
from PySide6.QtGui import QImage
from pydantic import BaseModel, Field

from skellycam.models.cameras.camera_id import CameraId

FRAME_PAYLOAD_BYTES_HEADER = 'bqiq'
RAW_IMAGE_BYTES_HEADER = '4i'


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
        header_size = struct.calcsize(RAW_IMAGE_BYTES_HEADER)
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
        header = struct.pack(RAW_IMAGE_BYTES_HEADER, self.width, self.height, self.channels, len(self.data_type))
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

    def to_bytes(self) -> bytes:
        byte_string = struct.pack(FRAME_PAYLOAD_BYTES_HEADER, self.success, self.timestamp_ns, self.frame_number,
                                  self.camera_id)
        return byte_string + self.raw_image.to_bytes()

    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        header_size = struct.calcsize(FRAME_PAYLOAD_BYTES_HEADER)
        success, timestamp_ns, frame_number, camera_id = struct.unpack(FRAME_PAYLOAD_BYTES_HEADER,
                                                                       byte_obj[:header_size])
        image = RawImage.from_bytes(byte_obj[header_size:])
        return cls(success=success,
                   timestamp_ns=timestamp_ns,
                   frame_number=frame_number,
                   camera_id=camera_id,
                   raw_image=image)

    def to_q_image(self) -> QImage:
        return self.raw_image.to_q_image()


class MultiFramePayload(BaseModel):
    frames: Dict[str, Optional[FramePayload]]

    @classmethod
    def create(cls, camera_ids: List[CameraId], **kwargs):
        return cls(frames={camera_id: None for camera_id in camera_ids},
                   **kwargs)

    @property
    def camera_ids(self) -> List[CameraId]:
        return [CameraId(camera_id) for camera_id in self.frames.keys()]

    @property
    def full(self):
        return not any([frame is None for frame in self.frames.values()])

    def add_frame(self, frame: FramePayload):
        self.frames[str(frame.camera_id)] = frame

    def to_bytes(self) -> bytes:
        frames_data = [(index, frame.to_bytes()) for index, frame in enumerate(self.frames.values()) if
                       frame is not None]
        number_of_frames = len(frames_data)

        # We'll save the indices of the non-None frames, as well as their lengths
        header_info = [(index, len(frame_bytes)) for index, frame_bytes in frames_data]
        frames_bytes = b''.join([frame_bytes for _, frame_bytes in frames_data])

        # Header will be number of frames, followed by (index, length) pairs for each frame
        header = struct.pack('i' + 'ii' * number_of_frames, number_of_frames, *itertools.chain(*header_info))

        return header + frames_bytes


    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        number_of_frames = struct.unpack('i', byte_obj[:4])[0]
        byte_obj = byte_obj[4:]

        header_info = struct.unpack('ii' * number_of_frames, byte_obj[:8 * number_of_frames])
        byte_obj = byte_obj[8 * number_of_frames:]

        # Unpack indices and lengths from header info
        indices, lengths = header_info[::2], header_info[1::2]

        frames = []
        byte_offset = 0
        for index, length in zip(indices, lengths):
            frame_bytes = byte_obj[byte_offset:byte_offset + length]
            frame = FramePayload.from_bytes(frame_bytes) if frame_bytes != b"" else None
            frames.append(frame)
            byte_offset += length

        return cls(frames={frame.camera_id: frame for frame in frames})

if __name__ == "__main__":
    from skellycam.tests.test_frame_payload import test_frame_payload_to_and_from_bytes, \
        test_raw_image_to_and_from_bytes, test_multi_frame_payload_to_and_from_bytes

    test_raw_image_to_and_from_bytes()
    print("RawImage tests passed!")
    test_frame_payload_to_and_from_bytes()
    print("FramePayload tests passed!")
    test_multi_frame_payload_to_and_from_bytes()
    print("MultiFramePayload tests passed!")
