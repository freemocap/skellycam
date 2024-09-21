import struct
from typing import Tuple, Any, List

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE, \
    FRAME_METADATA_DTYPE, DEFAULT_IMAGE_DTYPE


class FramePayloadDTO(BaseModel):
    """
    Lightweight data transfer object for FramePayload
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_data: np.ndarray
    image_shape: Tuple[int, int, int]

    metadata: np.ndarray


    def to_bytes_list(self) -> List[Any]:
        return [self._shape_to_bytes(self.image_shape),
                self.image_data.tobytes(),
                self.metadata.tobytes()]

    @classmethod
    def from_bytes_list(cls, bytes_list: List[Any]) -> 'FramePayloadDTO':
        image_shape = cls._bytes_to_shape(bytes_list[0], 3)
        image_data = np.frombuffer(bytes_list[1], dtype=DEFAULT_IMAGE_DTYPE).reshape(image_shape)

        metadata = np.frombuffer(bytes_list[2], dtype=FRAME_METADATA_DTYPE).reshape(FRAME_METADATA_SHAPE)

        return cls(image_data=image_data,
                   metadata=metadata,
                   image_shape=image_shape)

    @classmethod
    def create(cls, image: np.ndarray, metadata: np.ndarray):
        return cls(image_data=image,
                   image_shape=image.shape,
                   metadata=metadata,
                   metadata_shape=metadata.shape)

    @staticmethod
    def _shape_to_bytes(shape: Tuple[int, ...]) -> bytes:
        return struct.pack(f'{len(shape)}i', *shape)

    @staticmethod
    def _bytes_to_shape(shape_bytes: bytes, ndim: int) -> Tuple[int, ...]:
        return struct.unpack(f'{ndim}i', shape_bytes)

class FramePayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image: np.ndarray
    metadata: np.ndarray

    @classmethod
    def from_dto(cls, dto: FramePayloadDTO):
        image = dto.image
        metadata = dto.metadata
        instance = cls(image=image, metadata=metadata)
        if instance.metadata.shape != FRAME_METADATA_SHAPE:
            raise ValueError(f"Metadata shape mismatch - "
                             f"Expected: {FRAME_METADATA_SHAPE}, "
                             f"Actual: {metadata.shape}")
        return instance

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
