import logging
import time

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer, \
    SharedMemoryRingBufferDTO
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, FRAME_METADATA_SHAPE, DEFAULT_IMAGE_DTYPE

logger = logging.getLogger(__name__)


class FramePayloadSharedMemoryRingBufferDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm_dto: SharedMemoryRingBufferDTO
    metadata_shm_dto: SharedMemoryRingBufferDTO


class FramePayloadSharedMemoryRingBuffer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm: SharedMemoryRingBuffer
    metadata_shm: SharedMemoryRingBuffer
    read_only: bool

    @classmethod
    def create(
            cls,
            camera_config: CameraConfig,
            read_only: bool,
            buffer_length: int = 100,
    ):
        example_image = np.zeros(camera_config.image_shape, dtype=np.uint8)
        example_metadata = np.zeros(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)
        image_shm = SharedMemoryRingBuffer.create(
            example_payload=example_image,
            ring_buffer_length=buffer_length,
            dtype=DEFAULT_IMAGE_DTYPE,
            read_only=read_only,
        )
        metadata_shm = SharedMemoryRingBuffer.create(
            example_payload=example_metadata,
            dtype=FRAME_METADATA_DTYPE,
            ring_buffer_length=buffer_length,
            read_only=read_only,
        )

        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )

    @classmethod
    def recreate(cls,
                 dto: FramePayloadSharedMemoryRingBufferDTO,
                 read_only: bool, ):
        image_shm = SharedMemoryRingBuffer.recreate(
            dto=dto.image_shm_dto,
            read_only=read_only,
        )
        metadata_shm = SharedMemoryRingBuffer.recreate(
            dto=dto.metadata_shm_dto,
            read_only=read_only,
        )
        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )

    @property
    def ready_to_read(self):
        return self.image_shm.ready_to_read and self.metadata_shm.ready_to_read

    @property
    def new_frame_available(self):
        return self.image_shm.new_data_available and self.metadata_shm.new_data_available

    def to_dto(self) -> FramePayloadSharedMemoryRingBufferDTO:
        return FramePayloadSharedMemoryRingBufferDTO(
            image_shm_dto=self.image_shm.to_dto(),
            metadata_shm_dto=self.metadata_shm.to_dto(),
        )

    def put_frame(self, image: np.ndarray, metadata: np.ndarray, overwrite: bool = False):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        metadata[FRAME_METADATA_MODEL.COPY_TO_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.image_shm.put_data(image, overwrite=overwrite)
        self.metadata_shm.put_data(metadata, overwrite=overwrite)


    def retrieve_latest_frame(self) -> FramePayload:
        image = self.image_shm.get_latest_payload()
        metadata = self.metadata_shm.get_latest_payload()
        metadata[FRAME_METADATA_MODEL.COPY_FROM_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()

        return FramePayload(image=image, metadata=metadata)

    def retrieve_next_frame(self) -> FramePayload:
        image = self.image_shm.get_next_payload()
        metadata = self.metadata_shm.get_next_payload()
        metadata[FRAME_METADATA_MODEL.COPY_FROM_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        return FramePayload(image=image, metadata=metadata)

    def close(self):
        self.image_shm.close()
        self.metadata_shm.close()

    def unlink(self):
        self.image_shm.unlink()
        self.metadata_shm.unlink()
