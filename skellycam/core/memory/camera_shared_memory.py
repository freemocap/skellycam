import logging
from multiprocessing import shared_memory
from typing import List, Tuple

import numpy as np
from pydantic import BaseModel

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.frames.frame_payload import FramePayload, BYTES_PER_PIXEL

logger = logging.getLogger(__name__)


class CameraSharedMemoryModel(BaseModel):
    camera_config: CameraConfig
    buffer_size: int
    image_shape: Tuple[int, int, int]
    bytes_per_pixel: int = BYTES_PER_PIXEL
    unhydrated_payload_size: int
    next_index: int = 0
    shm: shared_memory.SharedMemory

    class Config:
        arbitrary_types_allowed = True

    @property
    def image_size(self) -> int:
        return np.prod(self.image_shape) * self.bytes_per_pixel

    @property
    def shared_memory_name(self):
        return self.shm.name

    @property
    def payload_size(self) -> int:
        return self.unhydrated_payload_size + self.image_size

    @property
    def offsets(self) -> List[int]:
        return list(np.arange(0, self.buffer_size, self.payload_size))

    @property
    def camera_id(self):
        return self.camera_config.camera_id

    @classmethod
    def from_config(cls,
                    camera_config: CameraConfig,
                    buffer_size: int,
                    shared_memory_name: str = None,
                    **kwargs
                    ):
        shm = cls._get_or_create_shared_memory(camera_id=camera_config.camera_id,
                                               buffer_size=buffer_size,
                                               shared_memory_name=shared_memory_name)

        image_size, unhydrated_pyload_size = cls._calculate_buffer_sizes(camera_config)

        return cls(camera_config=camera_config,
                   buffer_size=buffer_size,
                   image_shape=camera_config.image_shape,
                   unhydrated_payload_size=unhydrated_pyload_size,
                   shm=shm,
                   **kwargs)

    @classmethod
    def _get_or_create_shared_memory(cls,
                                     camera_id: CameraId,
                                     buffer_size: int,
                                     shared_memory_name: str):
        if shared_memory_name:
            logger.trace(
                f"RETRIEVING shared memory buffer for Camera{camera_id} - (Name: {shared_memory_name}, Size: {buffer_size})")
            return shared_memory.SharedMemory(name=shared_memory_name)
        else:
            logger.trace(
                f"CREATING shared memory buffer for Camera {camera_id} - (Name: {shared_memory_name}, Size: {buffer_size})")
            return shared_memory.SharedMemory(create=True,
                                              size=buffer_size)

    @staticmethod
    def _calculate_buffer_sizes(camera_config: CameraConfig,
                                payload_model: BaseModel = FramePayload) -> Tuple[int, int]:
        image_resolution = camera_config.resolution
        color_channels = camera_config.color_channels
        dummy_image = np.random.randint(0, 255, size=(image_resolution.height, image_resolution.width, color_channels))
        dummy_frame = payload_model.create_dummy(image=dummy_image)
        image_size_number_of_bytes = np.prod(dummy_image.shape) * BYTES_PER_PIXEL
        unhydrated_payload_number_of_bytes = len(dummy_frame.to_unhydrated_bytes())
        return (image_size_number_of_bytes, unhydrated_payload_number_of_bytes)


class CameraSharedMemory(CameraSharedMemoryModel):
    def put_frame(self, frame: FramePayload) -> int:

        if not frame.hydrated:
            raise ValueError(f"Frame payload for {self.camera_id} is must be hydrated before storing in shared memory.")

        payload_bytes = frame.to_buffer()
        if not len(payload_bytes) == self.payload_size:
            raise ValueError(f"Payload size mismatch for {self.camera_id} - "
                             f"Expected: {self.payload_size}, "
                             f"Actual: {len(payload_bytes)}")

        offset = self.offsets[self.next_index]
        if offset + self.payload_size > self.buffer_size:
            self.next_index = 0
            offset = self.offsets[self.next_index]

        self.shm.buf[offset:offset + self.payload_size] = payload_bytes
        index = self.next_index
        self.next_index += 1
        return index



    def retrieve_frame(self, index: int) -> FramePayload:

        if index >= len(self.offsets) or index < 0:
            raise ValueError(f"Index {index} out of range for {self.camera_id}")
        offset = self.offsets[index]
        payload_buffer = bytearray(self.shm.buf[offset:offset + self.payload_size])
        return FramePayload.from_buffer(buffer=payload_buffer,
                                        image_shape=self.image_shape)




    def _increment_index(self):
        self.next_index += 1
        if self.next_index >= len(self.offsets):
            self.next_index = 0