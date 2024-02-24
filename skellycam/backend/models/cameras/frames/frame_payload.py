import struct
from io import BytesIO
from typing import Literal

import cv2
import msgpack
import numpy as np
from PIL.Image import Image
from PySide6.QtGui import QImage
from pydantic import BaseModel, Field
from tabulate import tabulate


FRAME_PAYLOAD_BYTES_HEADER = "bqiq"
RAW_IMAGE_BYTES_HEADER = "5i"


class RawImage(BaseModel):
    image_bytes: bytes
    width: int
    height: int
    channels: int
    data_type: str
    compression: Literal["RAW", "JPEG", "PNG"] = Field(default="RAW")

    @classmethod
    def from_image(
        cls, image: np.ndarray, compression: Literal["RAW", "JPEG", "PNG"] = "RAW"
    ):
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
        (
            width,
            height,
            channels,
            data_type_length,
            compression_type_length,
        ) = struct.unpack(RAW_IMAGE_BYTES_HEADER, byte_obj[:header_size])

        data_type_start = header_size
        data_type_end = data_type_start + data_type_length
        data_type = byte_obj[data_type_start:data_type_end].decode()

        compression_start = data_type_end
        compression_end = compression_start + compression_type_length
        compression = byte_obj[compression_start:compression_end].decode()
        image_bytes = byte_obj[compression_end:]
        return cls(
            image_bytes=image_bytes,
            width=width,
            height=height,
            channels=channels,
            data_type=data_type,
            compression=compression,
        )

    def get_image(self) -> np.ndarray:
        if self.compression == "RAW":
            return np.frombuffer(self.image_bytes, dtype=self.data_type).reshape(
                (self.height, self.width, self.channels)
            )
        else:
            image_mode = "L" if self.channels == 1 else "RGB"
            pil_image = Image.open(BytesIO(self.image_bytes)).convert(image_mode)
            return np.array(pil_image)

    def set_image(self, image: np.ndarray):
        self.image_bytes = image.tobytes()
        self.width = image.shape[1]
        self.height = image.shape[0]
        self.channels = image.shape[2]
        self.data_type = str(image.dtype)

    def to_bytes(self):
        header = (
            struct.pack(
                RAW_IMAGE_BYTES_HEADER,
                self.width,
                self.height,
                self.channels,
                len(self.data_type),
                len(self.compression),
            )
            + self.data_type.encode()
            + self.compression.encode()
        )
        return header + self.image_bytes

    def _compress_image(
        image: np.ndarray, compression: str, quality: int = 70
    ) -> bytes:
        match compression:
            case "JPEG":
                """Compresses the image using JPEG format and returns it as bytes."""
                pil_image = Image.fromarray(image)
                with BytesIO() as byte_stream:
                    pil_image.save(byte_stream, format="JPEG", quality=quality)
                    byte_stream.seek(0)
                    compressed_image_bytes = byte_stream.read()
                return compressed_image_bytes
            case "PNG":
                """Compresses the image using PNG format and returns it as bytes."""
                pil_image = Image.fromarray(image)
                with BytesIO() as byte_stream:
                    pil_image.save(byte_stream, format="PNG")
                    byte_stream.seek(0)
                    compressed_image_bytes = byte_stream.read()
                return compressed_image_bytes

    def to_q_image(self) -> QImage:
        return QImage(
            self.image_bytes,
            self.width,
            self.height,
            self.channels * self.width,
            QImage.Format_RGB888,
        )

    def to_msgpack(self) -> bytes:
        # Convert the RawImage instance to a dictionary suitable for serializing
        raw_image_dict = {
            "image_bytes": self.image_bytes,
            "width": self.width,
            "height": self.height,
            "channels": self.channels,
            "data_type": self.data_type,
            "compression": self.compression,
        }
        return msgpack.packb(raw_image_dict, use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_data: bytes):
        # Unpack the bytes using MessagePack to a dictionary
        raw_image_dict = msgpack.unpackb(msgpack_data, raw=False)
        # Use the dictionary to instantiate a RawImage object
        return cls(**raw_image_dict)


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
