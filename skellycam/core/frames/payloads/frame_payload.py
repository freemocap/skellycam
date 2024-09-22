import struct
from typing import Tuple, Any, List

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE, \
    FRAME_METADATA_DTYPE, DEFAULT_IMAGE_DTYPE

IMAGE_CHUNK_SIZE = 5*1024*1024   # 5MB #TODO - optimize this bad boi


class FramePayload(BaseModel):
    """
    Lightweight data transfer object for FramePayload
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: np.ndarray
    metadata: np.ndarray

    def to_bytes_list(self) -> List[Any]:
        ret = [self._shape_to_bytes(self.image.shape),
               b"IMAGE-START", ]
        ret.extend(self._split_bytestring_by_size(self.image.tobytes()))
        return ret + [
            b"IMAGE-END",
            self.metadata.tobytes()]

    @classmethod
    def from_bytes_list(cls, bytes_list: List[Any]) -> 'FramePayload':
        image_shape = cls._bytes_to_shape(bytes_list.pop(0), 3)
        popped = bytes_list.pop(0)
        if popped != b"IMAGE-START":
            raise ValueError(f"Unexpected element in FramePayloadDTO bytes list, expected 'IMAGE-START', got {popped}")
        image_bytes_list = []
        while True:
            popped = bytes_list.pop(0)
            if popped != b"IMAGE-END":
                image_bytes_list.append(popped)
            else:
                break
        image_bytes = cls._reconstruct_bytestring(image_bytes_list)
        image = np.frombuffer(image_bytes, dtype=DEFAULT_IMAGE_DTYPE).reshape(image_shape)

        metadata = np.frombuffer(bytes_list.pop(0), dtype=FRAME_METADATA_DTYPE).reshape(FRAME_METADATA_SHAPE).copy()

        if len(bytes_list) != 0:
            raise ValueError(f"Unexpected elements left-over in FramePayloadDTO bytes list: {bytes_list}")
        return cls(image=image,
                   metadata=metadata,
                   image_shape=image_shape)

    @classmethod
    def create(cls, image: np.ndarray, metadata: np.ndarray):
        return cls(image=image,
                   image_shape=image.shape,
                   metadata=metadata,
                   metadata_shape=metadata.shape)

    @staticmethod
    def _shape_to_bytes(shape: Tuple[int, ...]) -> bytes:
        return struct.pack(f'{len(shape)}i', *shape)

    @staticmethod
    def _bytes_to_shape(shape_bytes: bytes, ndim: int) -> Tuple[int, ...]:
        return struct.unpack(f'{ndim}i', shape_bytes)

    @staticmethod
    def _split_bytestring_by_size(bs: bytes, chunk_size: int = IMAGE_CHUNK_SIZE) -> list[bytes]:
        return [bs[i:i + chunk_size] for i in range(0, len(bs), chunk_size)]

    @staticmethod
    def _reconstruct_bytestring(chunks: list[bytes]) -> bytes:
        return b''.join(chunks)

    @property
    def camera_id(self):
        return self.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]

    @property
    def frame_number(self):
        return self.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]

    @property
    def height(self):
        return self.image.shape[0]

    @property
    def width(self):
        return self.image.shape[1]

    def __eq__(self, other: "FramePayload"):
        return np.array_equal(self.image, other.image) and np.array_equal(self.metadata, other.metadata)

    def __str__(self):
        print_str = (
            f"Camera{self.camera_id}: Image shape: {self.image.shape}, "
        )
        return print_str
