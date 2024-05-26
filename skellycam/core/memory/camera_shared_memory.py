import logging
import time
from multiprocessing import shared_memory
from typing import Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.memory.shared_memory_element import SharedMemoryElement

logger = logging.getLogger(__name__)


class CameraSharedMemory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_shm_element: SharedMemoryElement
    metadata_shm_element: SharedMemoryElement

    @classmethod
    def create(
            cls,
            camera_config: CameraConfig,
    ):
        image_shm_element = SharedMemoryElement(
            payload_size_bytes=camera_config.image_size_bytes,
            buffer=np.ndarray(camera_config.image_shape, dtype=np.uint8),
            shm=shared_memory.SharedMemory(size=camera_config.image_size_bytes, create=True),
        )

        metadata_shm_element = SharedMemoryElement(
            payload_size_bytes=FRAME_METADATA_MODEL.size_in_bytes,
            buffer=np.ndarray((FRAME_METADATA_MODEL.number_of_elements,), dtype=np.uint64),
            shm=shared_memory.SharedMemory(size=FRAME_METADATA_MODEL.size_in_bytes, create=True),
        )

        return cls(
            image_buffer=image_buffer,
            image_shm=image_shm,
            image_size_bytes=image_buffer_size,
            metadata_buffer=metadata_buffer,
            metadata_size_bytes=FRAME_METADATA_MODEL.size_in_bytes,
            metadata_shm=metadata_shm,
        )

    @classmethod
    def recreate(cls, camera_config: CameraConfig, shared_memory_names: SharedMemoryNames):
        image_shm = shared_memory.SharedMemory(name=shared_memory_names.image_shm_name)
        image_buffer = np.ndarray(camera_config.image_shape, dtype=np.uint8, buffer=image_shm.buf)

        metadata_shm = shared_memory.SharedMemory(name=shared_memory_names.metadata_shm_name)
        metadata_buffer = np.ndarray(
            (FRAME_METADATA_MODEL.number_of_elements,), dtype=np.uint64, buffer=metadata_shm.buf
        )

        return cls(
            image_buffer=image_buffer,
            metadata_buffer=metadata_buffer,
            image_shm=image_shm,
            metadata_shm=metadata_shm,
        )

    @property
    def shared_memory_names(self) -> SharedMemoryNames:
        return SharedMemoryNames(image_shm_name=self.image_shm.name, metadata_shm_name=self.metadata_shm.name)

    def put_new_frame(self, image: np.ndarray, metadata: np.ndarray):
        metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS] = time.perf_counter_ns()  # copy_timestamp_ns
        self.image_buffer[:] = image
        self.metadata_buffer[:] = metadata
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID]} put wrote frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER]} to shared memory"
        )

    def retrieve_frame(self) -> Tuple[memoryview, memoryview]:
        image_mv = memoryview(self.image_buffer)
        metadata_mv = memoryview(self.metadata_buffer)
        logger.loop(
            f"Camera {metadata_mv[FRAME_METADATA_MODEL.CAMERA_ID]} retrieved frame#{metadata_mv[FRAME_METADATA_MODEL.FRAME_NUMBER]} from shared memory"
        )
        return image_mv, metadata_mv

    def close(self):
        self.image_shm.close()
        self.metadata_shm.close()

    def unlink(self):
        self.image_shm.unlink()
        self.metadata_shm.unlink()
