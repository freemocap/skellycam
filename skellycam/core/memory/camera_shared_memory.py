import logging
import time

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE, FRAME_METADATA_DTYPE
from skellycam.core.frames.frame_payload import FramePayloadDTO
from skellycam.core.memory.shared_memory_element import SharedMemoryElement

logger = logging.getLogger(__name__)


class SharedMemoryNames(BaseModel):
    image_shm_name: str
    metadata_shm_name: str


class CameraSharedMemory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    camera_config: CameraConfig
    image_shm: SharedMemoryElement
    metadata_shm: SharedMemoryElement

    @classmethod
    def create(
            cls,
            camera_config: CameraConfig,
    ):
        image_shm = SharedMemoryElement.create(
            shape=camera_config.image_shape,
            dtype=np.uint8,
        )
        metadata_shm = SharedMemoryElement.create(
            shape=FRAME_METADATA_SHAPE,
            dtype=FRAME_METADATA_DTYPE,
        )

        return cls(
            camera_config=camera_config,
            image_shm=image_shm,
            metadata_shm=metadata_shm,
        )

    @classmethod
    def recreate(cls,
                 camera_config: CameraConfig,
                 shared_memory_names: SharedMemoryNames):
        image_shm = SharedMemoryElement.recreate(
            shared_memory_names.image_shm_name,
            shape=camera_config.image_shape,
            dtype=np.uint8,
        )
        metadata_shm = SharedMemoryElement.recreate(
            shared_memory_names.metadata_shm_name,
            shape=FRAME_METADATA_SHAPE,
            dtype=FRAME_METADATA_DTYPE,
        )
        return cls(
            camera_config=camera_config,
            image_shm=image_shm,
            metadata_shm=metadata_shm,
        )

    @property
    def shared_memory_names(self) -> SharedMemoryNames:
        return SharedMemoryNames(image_shm_name=self.image_shm.name, metadata_shm_name=self.metadata_shm.name)

    def put_new_frame(self, image: np.ndarray, metadata: np.ndarray):
        metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.image_shm.copy_into_buffer(image)
        self.metadata_shm.copy_into_buffer(metadata)
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} put wrote frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} to shared memory"
        )

    def retrieve_frame(self) -> FramePayloadDTO:
        image = self.image_shm.copy_from_buffer()
        metadata = self.metadata_shm.copy_from_buffer()
        metadata[FRAME_METADATA_MODEL.COPY_FROM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} retrieved frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} from shared memory"
        )
        return FramePayloadDTO(image=image, metadata=metadata)

    def close(self):
        self.image_shm.close()
        self.metadata_shm.close()

    def unlink(self):
        self.image_shm.unlink()
        self.metadata_shm.unlink()
