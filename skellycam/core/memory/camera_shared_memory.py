import logging
import time
from multiprocessing import shared_memory
from typing import Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_BUFFER_SIZE, FRAME_METADATA_ELEMENTS

logger = logging.getLogger(__name__)


class SharedMemoryNames(BaseModel):
    image_shm_name: str
    metadata_shm_name: str


class CameraSharedMemory(BaseModel):
    image_buffer: np.ndarray
    metadata_buffer: np.ndarray
    image_shm: shared_memory.SharedMemory
    metadata_shm: shared_memory.SharedMemory
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls, camera_config: CameraConfig, ):
        image_buffer_size = camera_config.image_size_bytes
        image_shm = shared_memory.SharedMemory(size=image_buffer_size, create=True)
        image_buffer = np.ndarray(camera_config.image_shape, dtype=np.uint8, buffer=image_shm.buf)
        metadata_shm = shared_memory.SharedMemory(size=FRAME_METADATA_BUFFER_SIZE, create=True)
        metadata_buffer = np.ndarray((7,), dtype=np.uint64, buffer=metadata_shm.buf)

        return cls(image_buffer=image_buffer,
                   metadata_buffer=metadata_buffer,
                   image_shm=image_shm,
                   metadata_shm=metadata_shm,
                   )

    @classmethod
    def recreate(cls, camera_config: CameraConfig, shared_memory_names: SharedMemoryNames):
        image_shm = shared_memory.SharedMemory(name=shared_memory_names.image_shm_name)
        image_buffer = np.ndarray(camera_config.image_shape, dtype=np.uint8, buffer=image_shm.buf)

        metadata_shm = shared_memory.SharedMemory(name=shared_memory_names.metadata_shm_name)
        metadata_buffer = np.ndarray((FRAME_METADATA_ELEMENTS,), dtype=np.uint64, buffer=metadata_shm.buf)

        return cls(image_buffer=image_buffer,
                   metadata_buffer=metadata_buffer,
                   image_shm=image_shm,
                   metadata_shm=metadata_shm,
                   )

    @property
    def shared_memory_names(self) -> SharedMemoryNames:
        return SharedMemoryNames(image_shm_name=self.image_shm.name,
                                 metadata_shm_name=self.metadata_shm.name)

    def put_new_frame(self,
                      image: np.ndarray,
                      metadata: np.ndarray):
        metadata[-1] = time.perf_counter_ns()  # copy_timestamp_ns
        self.image_buffer[:] = image
        self.metadata_buffer[:] = metadata
        logger.loop(f"Camera {metadata[0]} put wrote frame#{metadata[1]} to shared memory")

    def retrieve_frame(self) -> Tuple[memoryview, memoryview]:
        image_mv = memoryview(self.image_buffer)
        metadata_mv = memoryview(self.metadata_buffer)
        logger.loop(f"Camera {metadata_mv[0]} retrieved frame#{metadata_mv[1]} from shared memory")
        return image_mv, metadata_mv

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()
