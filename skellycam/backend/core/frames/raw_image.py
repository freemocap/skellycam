import struct
from io import BytesIO
from typing import Literal

import msgpack
import numpy as np
from PIL.Image import Image
from PySide6.QtGui import QImage
from pydantic import BaseModel, Field

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
