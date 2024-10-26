import logging
import time
from typing import Dict

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_element import SharedMemoryElement
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_ring_buffer import SharedMemoryRingBuffer
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, FRAME_METADATA_SHAPE, DEFAULT_IMAGE_DTYPE

logger = logging.getLogger(__name__)


class SharedMemoryNames(BaseModel):
    image_shm_name: str
    metadata_shm_name: str


GroupSharedMemoryNames = Dict[CameraId, SharedMemoryNames]


class SingleSlotCameraSharedMemory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm: SharedMemoryElement|SharedMemoryRingBuffer
    metadata_shm: SharedMemoryElement|SharedMemoryRingBuffer
    read_only: bool

    @classmethod
    def create(
            cls,
            camera_config: CameraConfig,
            read_only: bool,
    ):
        image_shm = SharedMemoryElement.create(
            shape=camera_config.image_shape,
            dtype=DEFAULT_IMAGE_DTYPE,
        )
        metadata_shm = SharedMemoryElement.create(
            shape=FRAME_METADATA_SHAPE,
            dtype=FRAME_METADATA_DTYPE,
        )

        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )

    @classmethod
    def recreate(cls,
                 camera_config: CameraConfig,
                 shared_memory_names: SharedMemoryNames,
                 read_only: bool, ):
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
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )

    @property
    def shared_memory_names(self) -> SharedMemoryNames:
        return SharedMemoryNames(image_shm_name=self.image_shm.name, metadata_shm_name=self.metadata_shm.name)

    def put_frame(self, image: np.ndarray, metadata: np.ndarray):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.image_shm.put_data(image)
        self.metadata_shm.put_data(metadata)
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} put frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} into shared memory"
        )

    def retrieve_frame(self) -> FramePayload:

        image = self.image_shm.get_data()
        metadata = self.metadata_shm.get_data()
        metadata[FRAME_METADATA_MODEL.COPY_FROM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} retrieved frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} from shared memory"
        )
        return FramePayload.create(image=image, metadata=metadata)

    def close(self):
        self.image_shm.close()
        self.metadata_shm.close()

    def unlink(self):
        self.image_shm.unlink()
        self.metadata_shm.unlink()
