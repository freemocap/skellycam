import struct
from dataclasses import dataclass
from typing import Tuple, Any, List

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE, \
    FRAME_METADATA_DTYPE, DEFAULT_IMAGE_DTYPE, create_empty_frame_metadata

IMAGE_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB #TODO - optimize this bad boi


@dataclass
class FramePayloadBuffer:
    buffer: np.ndarray

    @classmethod
    def from_frame_payload(cls, frame_payload: 'FramePayload') -> 'FramePayloadBuffer':
        image_shape = frame_payload.image.shape
        if len(image_shape) == 2:
            image_shape = (*image_shape, 1)

        # Flatten the image and convert to the appropriate dtype
        image_vector = frame_payload.image.astype(DEFAULT_IMAGE_DTYPE).ravel()

        # Assume metadata is already in the correct dtype and shape
        metadata_flat = frame_payload.metadata.astype(FRAME_METADATA_DTYPE).ravel()

        buffer = np.concatenate([metadata_flat, np.array(image_shape, dtype=np.int64), image_vector])

        return cls(buffer=buffer)

    def to_frame_payload(self) -> 'FramePayload':
        # Extract metadata from buffer
        metadata_size = np.prod(FRAME_METADATA_SHAPE)
        metadata_end = metadata_size
        metadata = self.buffer[:metadata_end].astype(FRAME_METADATA_DTYPE).reshape(FRAME_METADATA_SHAPE).copy()

        # Extract image shape from buffer
        image_shape_start = metadata_end
        image_shape_end = image_shape_start + 3
        image_shape = tuple(map(int, self.buffer[image_shape_start:image_shape_end]))

        # Extract image data from buffer
        image_data_start = image_shape_end
        image_buffer = self.buffer[image_data_start:].astype(DEFAULT_IMAGE_DTYPE)
        image = image_buffer.reshape(image_shape)

        return FramePayload(image=image, metadata=metadata)

class FramePayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: np.ndarray
    metadata: np.ndarray

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

    @classmethod
    def create(cls, image: np.ndarray, metadata: np.ndarray):
        return cls(image=image,
                   image_shape=image.shape,
                   metadata=metadata,
                   metadata_shape=metadata.shape)

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

    def to_bytes_list(self) -> List[Any]:
        ret = [self._shape_to_bytes(self.image.shape),
               b"IMAGE-START", ]
        ret.extend(self._split_bytestring_by_size(self.image.tobytes()))
        return ret + [
            b"IMAGE-END",
            self.metadata.tobytes()]

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

    def __eq__(self, other: "FramePayload"):
        return np.array_equal(self.image, other.image) and np.array_equal(self.metadata, other.metadata)

    def __str__(self):
        print_str = (
            f"Camera{self.camera_id}: Image shape: {self.image.shape}, "
        )
        return print_str


def create_dummy_frame_payload(camera_id: CameraId = CameraId(0)):
    return FramePayload(image=np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8),
                        metadata=create_empty_frame_metadata(camera_id=camera_id, frame_number=0))

if __name__ == "__main__":
    og_frame = create_dummy_frame_payload()
    array = FramePayloadBuffer.from_frame_payload(og_frame)
    new_frame = array.to_frame_payload()
    if not og_frame == new_frame:
        raise ValueError("FramePayloadBuffer failed to convert back and forth")
    print("FramePayloadBuffer passed test")