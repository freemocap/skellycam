import logging
import pickle
from multiprocessing import shared_memory
from typing import List

import numpy as np
from pydantic import BaseModel

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CameraSharedMemoryModel(BaseModel):
    camera_config: CameraConfig
    buffer_size: int
    payload_model: BaseModel = FramePayload
    payload_buffer_offsets: List[int]
    next_index: int = 0
    shm: shared_memory.SharedMemory

    @property
    def shared_memory_name(self):
        return self.shm.name

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
        offsets = cls._calculate_buffer_offsets(buffer_size, camera_config)

        if shared_memory_name:
            logger.trace(
                f"Retrieving shared memory buffer for {camera_config.camera_id} (Name: {shared_memory_name}, Size: {buffer_size})")
            shm = shared_memory.SharedMemory(name=shared_memory_name)
        else:
            logger.trace(
                f"Creating shared memory buffer for {camera_config.camera_id} (Name: {shared_memory_name}, Size: {buffer_size})")
            shm = shared_memory.SharedMemory(create=True,
                                             size=buffer_size)

        return cls(camera_config=camera_config,
                   buffer_size=buffer_size,
                   payload_buffer_offsets=offsets,
                   **kwargs)

    @classmethod
    def _calculate_buffer_offsets(cls,
                                  buffer_size: int,
                                  camera_config: CameraConfig) -> List[int]:
        image_resolution = camera_config.image_resolution
        color_channels = camera_config.color_channels
        image_dtype = np.uint8
        image_size_bytes = np.prod((image_resolution.height,
                                    image_resolution.width,
                                    color_channels)) * np.dtype(image_dtype).itemsize

        unhydrated_payload_size = len(pickle.dumps(cls.payload_model.create_dummy()))  # w/o image data

        total_payload_size = unhydrated_payload_size + image_size_bytes
        return list(np.arange(0, buffer_size, total_payload_size))



class CameraSharedMemory(CameraSharedMemoryModel):
    def put_payload(self, payload: FramePayload) -> int:
        image_data = payload.image.tobytes()
        payload_data = payload.to_unhydrated_bytes()
        if self.next_index >= len(self.payload_buffer_offsets):
            self.next_index = 0
        offset = self.payload_buffer_offsets[self.next_index]

        self.shm.buf[offset:offset + len(payload)] = pickle.dumps(payload)
        self.next_index += 1
        return self.next_index

    def get_payload(self, index: int) -> FramePayload:
        if index >= len(self.payload_buffer_offsets):
            raise ValueError(f"Index out of range for {self.camera_id}")
        offset = self.payload_buffer_offsets[index]
        return pickle.loads(self.shm.buf[offset:offset + len(self.payload_model.create_dummy())])

    def __del__(self):
        self.shm.close()
        self.shm.unlink()