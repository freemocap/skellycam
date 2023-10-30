import itertools
import struct
from io import BytesIO
from typing import Dict, Optional, List, Literal

import cv2
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage
from pydantic import BaseModel, Field
from tabulate import tabulate

from skellycam.models.cameras.camera_id import CameraId

FRAME_PAYLOAD_BYTES_HEADER = 'bqiq'
RAW_IMAGE_BYTES_HEADER = '5i'


class RawImage(BaseModel):
    image_bytes: bytes
    width: int
    height: int
    channels: int
    data_type: str
    compression: Literal["RAW", "JPEG", "PNG"] = Field(default="RAW")

    @classmethod
    def from_image(cls, image: np.ndarray, compression: Literal["RAW", "JPEG", "PNG"] = "RAW"):
        if compression == "RAW":
            return cls(
                image_bytes=image.tobytes(),
                width=image.shape[1],
                height=image.shape[0],
                channels=image.shape[2],
                data_type=str(image.dtype),
            )

        return cls(
            image_bytes=cls._compress_image(image=image, compression=compression),
            width=image.shape[1],
            height=image.shape[0],
            channels=image.shape[2],
            data_type=str(image.dtype),
            compression=compression,
        )

    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        header_size = struct.calcsize(RAW_IMAGE_BYTES_HEADER)
        width, height, channels, data_type_length, compression_type_length = struct.unpack(RAW_IMAGE_BYTES_HEADER,
                                                                                           byte_obj[:header_size])

        data_type_start = header_size
        data_type_end = data_type_start + data_type_length
        data_type = byte_obj[data_type_start:data_type_end].decode()

        compression_start = data_type_end
        compression_end = compression_start + compression_type_length
        compression = byte_obj[compression_start:compression_end].decode()
        image_bytes = byte_obj[compression_end:]
        return cls(image_bytes=image_bytes,
                   width=width,
                   height=height,
                   channels=channels,
                   data_type=data_type,
                   compression=compression)

    def get_image(self) -> np.ndarray:
        if self.compression == "RAW":
            return np.frombuffer(self.image_bytes, dtype=self.data_type).reshape(
                (self.height, self.width, self.channels))
        else:
            image_mode = 'L' if self.channels == 1 else 'RGB'
            pil_image = Image.open(BytesIO(self.image_bytes)).convert(image_mode)
            return np.array(pil_image)

    def set_image(self, image: np.ndarray):
        self.image_bytes = image.tobytes()
        self.width = image.shape[1]
        self.height = image.shape[0]
        self.channels = image.shape[2]
        self.data_type = str(image.dtype)

    def to_bytes(self):
        header = struct.pack(RAW_IMAGE_BYTES_HEADER,
                             self.width,
                             self.height,
                             self.channels,
                             len(self.data_type),
                             len(self.compression)) + self.data_type.encode() + self.compression.encode()
        return header + self.image_bytes

    def _compress_image(image: np.ndarray,
                        compression: str,
                        quality: int = 70) -> bytes:
        match compression:
            case "JPEG":
                """Compresses the image using JPEG format and returns it as bytes."""
                pil_image = Image.fromarray(image)
                with BytesIO() as byte_stream:
                    pil_image.save(byte_stream, format='JPEG', quality=quality)
                    byte_stream.seek(0)
                    compressed_image_bytes = byte_stream.read()
                return compressed_image_bytes
            case "PNG":
                """Compresses the image using PNG format and returns it as bytes."""
                pil_image = Image.fromarray(image)
                with BytesIO() as byte_stream:
                    pil_image.save(byte_stream, format='PNG')
                    byte_stream.seek(0)
                    compressed_image_bytes = byte_stream.read()
                return compressed_image_bytes

    def to_q_image(self) -> QImage:
        return QImage(self.image_bytes,
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

    def get_resolution(self) -> tuple[int, int]:
        return self.raw_image.width, self.raw_image.height

    def get_image(self) -> np.ndarray:
        return self.raw_image.get_image()

    def set_image(self, image: np.ndarray):
        self.raw_image = RawImage.from_image(image=image, compression=self.raw_image.compression)


    @classmethod
    def create(cls,
               success: bool,
               image: np.ndarray,
               timestamp_ns: int,
               frame_number: int,
               camera_id: int,
               compression: Literal["RAW", "JPEG", "PNG"] = "RAW"):
        return cls(
            success=success,
            raw_image=RawImage.from_image(image=image, compression=compression),
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id,
        )

    def compress(self, compression: Literal["JPEG", "PNG"]):
        self.raw_image = RawImage.from_image(image=self.raw_image.image, compression=compression)

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

    def resize(self, scale_factor: float):
        scaled_image = cv2.resize(self.get_image(), dsize=None, fx=scale_factor, fy=scale_factor)
        self.raw_image = RawImage.from_image(image=scaled_image, compression=self.raw_image.compression)

    def rotate(self, cv2_rotate_flag: int):
        rotated_image = cv2.rotate(self.get_image(), cv2_rotate_flag)
        self.raw_image = RawImage.from_image(image=rotated_image, compression=self.raw_image.compression)

class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]]

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

    def resize(self, scale_factor: float):
        for frame in self.frames.values():
            if frame is not None:
                frame.resize(scale_factor=scale_factor)
    def add_frame(self, frame: FramePayload):
        self.frames[frame.camera_id] = frame

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


def evaluate_multi_frame_compression():
    import time
    number_of_images = 4
    image_shape = (1920, 1080, 3)
    images = [np.random.randint(0, 255, image_shape, dtype=np.uint8) for _ in range(number_of_images)]

    compressed_results = {"add_frame_duration_ms": [],
                          "size_kb": []}
    uncompressed_results = {"add_frame_duration_ms": [],
                            "size_kb": []}

    for image in images:
        tik = time.perf_counter()
        uncompressed_frame = FramePayload.create(success=True,
                                                 image=image,
                                                 timestamp_ns=0,
                                                 frame_number=0,
                                                 camera_id=0)
        tok = time.perf_counter()
        duration_ms = (tok - tik) * 1000
        size_kb = len(uncompressed_frame.to_bytes()) / 1000
        uncompressed_results["add_frame_duration_ms"].append(duration_ms)
        uncompressed_results["size_kb"].append(size_kb)

        tik = time.perf_counter()
        compressed_frame = FramePayload.create(success=True,
                                               image=image,
                                               timestamp_ns=0,
                                               frame_number=0,
                                               camera_id=0,
                                               compression="JPEG")
        tok = time.perf_counter()
        duration_ms = (tok - tik) * 1000
        size_kb = len(compressed_frame.to_bytes()) / 1000
        compressed_results["add_frame_duration_ms"].append(duration_ms)
        compressed_results["size_kb"].append(size_kb)

    print(f"\nUncompressed Results:")
    print(tabulate(uncompressed_results, headers="keys", tablefmt="pretty"))
    print(f"\nCompressed Results:")
    print(tabulate(compressed_results, headers="keys", tablefmt="pretty"))


if __name__ == "__main__":
    from skellycam.tests.test_frame_payload import test_frame_payload_to_and_from_bytes, \
        test_raw_image_to_and_from_bytes, test_multi_frame_payload_to_and_from_bytes

    test_raw_image_to_and_from_bytes()
    print("RawImage tests passed!")
    test_frame_payload_to_and_from_bytes()
    print("FramePayload tests passed!")
    test_multi_frame_payload_to_and_from_bytes()
    print("MultiFramePayload to/from bytes tests passed!")
    evaluate_multi_frame_compression()
