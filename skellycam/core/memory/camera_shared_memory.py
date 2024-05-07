import logging
import pickle
from multiprocessing import shared_memory
from typing import List

import numpy as np
from pydantic import BaseModel

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CameraSharedMemoryModel(BaseModel):
    camera_config: CameraConfig
    buffer_size: int
    image_size: int
    unhydrated_payload_size: int
    payload_buffer_offsets: List[int]
    next_index: int = 0
    shm: shared_memory.SharedMemory

    @property
    def shared_memory_name(self):
        return self.shm.name

    @property
    def payload_size(self) -> int:
        return self.unhydrated_payload_size + self.image_size

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

        payload_size = cls._calculate_payload_size(camera_config.payload_model, camera_config)

        offsets = np.arange(0, buffer_size, payload_size)

        return cls(camera_config=camera_config,
                   buffer_size=buffer_size,
                   payload_size=payload_size,
                   offsets=offsets,
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
    def _calculate_payload_size(payload_model: FramePayload,
                                camera_config: CameraConfig) -> List[int]:
        image_resolution = camera_config.image_resolution
        color_channels = camera_config.color_channels
        image_dtype = np.uint8
        image_size_bytes = np.prod((image_resolution.height,
                                    image_resolution.width,
                                    color_channels)) * np.dtype(image_dtype).itemsize

        unhydrated_payload_size = len(pickle.dumps(payload_model.create_dummy()))  # w/o image data
        return unhydrated_payload_size + image_size_bytes


class CameraSharedMemory(CameraSharedMemoryModel):
    def put_frame_payload(self, frame: FramePayload) -> int:
        if not frame.hydrated:
            raise ValueError(f"Frame payload for {self.camera_id} is must be hydrated before storing in shared memory.")

        payload_bytes = frame.to_buffer()
        if not len(payload_bytes) == self.payload_size:
            raise ValueError(f"Payload size mismatch for {self.camera_id} - "
                             f"Expected: {self.payload_size}, "
                             f"Actual: {len(payload_bytes)}")

        if self.next_index >= len(self.payload_buffer_offsets):
            self.next_index = 0

        offset = self.payload_buffer_offsets[self.next_index]

        self.shm.buf[offset:offset + len(payload_bytes)] = payload_bytes
        self.next_index += 1
        return self.next_index

    def get_payload(self, index: int) -> FramePayload:
        if index >= len(self.payload_buffer_offsets) or index < 0:
            raise ValueError(f"Index {index} out of range for {self.camera_id}")
        offset = self.payload_buffer_offsets[index]
        payload_buffer = self.shm.buf[offset:offset + len(self.payload_model.create_dummy())]
        return FramePayload.from_buffer(payload_buffer)

    def __del__(self):
        self.shm.close()
        self.shm.unlink()
