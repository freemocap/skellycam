import struct
from typing import Literal

import cv2
import msgpack
import numpy as np
from PySide6.QtGui import QImage
from pydantic import BaseModel, Field
from tabulate import tabulate

from skellycam.backend.core.frames.raw_image import RawImage

FRAME_PAYLOAD_BYTES_HEADER = "bqiq"


class FramePayload(BaseModel):
    success: bool = Field(
        description="The `success` part of `success, image = cv2.VideoCapture.read()`"
    )
    raw_image: RawImage = Field(
        description="The raw image from `cv2.VideoCapture.read()`"
    )
    timestamp_ns: int = Field(
        description="The timestamp of the frame in nanoseconds,"
        " from `time.perf_counter_ns()`"
    )
    frame_number: int = Field(
        description="The frame number of the frame "
        "(`0` is the first frame pulled from this camera)"
    )
    camera_id: int = Field(
        description="The camera ID of the camera that this frame came from,"
        " e.g. `0` if this is the `cap = cv2.VideoCapture(0)` camera"
    )

    def get_resolution(self) -> tuple[int, int]:
        return self.raw_image.width, self.raw_image.height

    def get_image(self) -> np.ndarray:
        return self.raw_image.get_image()

    def set_image(self, image: np.ndarray):
        self.raw_image = RawImage.from_image(
            image=image, compression=self.raw_image.compression
        )

    @classmethod
    def create(
        cls,
        success: bool,
        image: np.ndarray,
        timestamp_ns: int,
        frame_number: int,
        camera_id: int,
        compression: Literal["RAW", "JPEG", "PNG"] = "RAW",
    ):
        return cls(
            success=success,
            raw_image=RawImage.from_image(image=image, compression=compression),
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id,
        )

    def compress(self, compression: Literal["JPEG", "PNG"]):
        self.raw_image = RawImage.from_image(
            image=self.raw_image.image, compression=compression
        )

    def to_bytes(self) -> bytes:
        byte_string = struct.pack(
            FRAME_PAYLOAD_BYTES_HEADER,
            self.success,
            self.timestamp_ns,
            self.frame_number,
            self.camera_id,
        )
        return byte_string + self.raw_image.to_bytes()

    def to_msgpack(self) -> bytes:
        # Convert the complex objects into simpler representations first
        raw_image_data = self.raw_image.to_dict()
        frame_payload_dict = {
            "success": self.success,
            "timestamp_ns": self.timestamp_ns,
            "frame_number": self.frame_number,
            "camera_id": self.camera_id,
            "raw_image": raw_image_data,
        }
        return msgpack.packb(frame_payload_dict, use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        payload_dict = msgpack.unpackb(msgpack_bytes, raw=False)
        # Create the RawImage from the dictionary data
        raw_image = RawImage(**payload_dict.pop("raw_image"))
        return cls(raw_image=raw_image, **payload_dict)

    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        header_size = struct.calcsize(FRAME_PAYLOAD_BYTES_HEADER)
        success, timestamp_ns, frame_number, camera_id = struct.unpack(
            FRAME_PAYLOAD_BYTES_HEADER, byte_obj[:header_size]
        )
        image = RawImage.from_bytes(byte_obj[header_size:])
        return cls(
            success=success,
            timestamp_ns=timestamp_ns,
            frame_number=frame_number,
            camera_id=camera_id,
            raw_image=image,
        )

    def to_q_image(self) -> QImage:
        return self.raw_image.to_q_image()

    def resize(self, scale_factor: float):
        scaled_image = cv2.resize(
            self.get_image(), dsize=None, fx=scale_factor, fy=scale_factor
        )
        self.raw_image = RawImage.from_image(
            image=scaled_image, compression=self.raw_image.compression
        )

    def rotate(self, cv2_rotate_flag: int):
        rotated_image = cv2.rotate(self.get_image(), cv2_rotate_flag)
        self.raw_image = RawImage.from_image(
            image=rotated_image, compression=self.raw_image.compression
        )


def evaluate_multi_frame_compression():
    import time

    number_of_images = 4
    image_shape = (1920, 1080, 3)
    images = [
        np.random.randint(0, 255, image_shape, dtype=np.uint8)
        for _ in range(number_of_images)
    ]

    compressed_results = {"add_frame_duration_ms": [], "size_kb": []}
    uncompressed_results = {"add_frame_duration_ms": [], "size_kb": []}

    for image in images:
        tik = time.perf_counter()
        uncompressed_frame = FramePayload.create(
            success=True, image=image, timestamp_ns=0, frame_number=0, camera_id=0
        )
        tok = time.perf_counter()
        duration_ms = (tok - tik) * 1000
        size_kb = len(uncompressed_frame.to_bytes()) / 1000
        uncompressed_results["add_frame_duration_ms"].append(duration_ms)
        uncompressed_results["size_kb"].append(size_kb)

        tik = time.perf_counter()
        compressed_frame = FramePayload.create(
            success=True,
            image=image,
            timestamp_ns=0,
            frame_number=0,
            camera_id=0,
            compression="JPEG",
        )
        tok = time.perf_counter()
        duration_ms = (tok - tik) * 1000
        size_kb = len(compressed_frame.to_bytes()) / 1000
        compressed_results["add_frame_duration_ms"].append(duration_ms)
        compressed_results["size_kb"].append(size_kb)

    print(f"\nUncompressed Results:")
    print(tabulate(uncompressed_results, headers="keys", tablefmt="pretty"))
    print(f"\nCompressed Results:")
    print(tabulate(compressed_results, headers="keys", tablefmt="pretty"))
