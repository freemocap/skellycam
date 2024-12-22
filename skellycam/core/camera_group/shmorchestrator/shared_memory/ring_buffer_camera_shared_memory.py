import logging
import time

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer, \
    SharedMemoryRingBufferDTO
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, FRAME_METADATA_SHAPE, DEFAULT_IMAGE_DTYPE

logger = logging.getLogger(__name__)


class RingBufferCameraSharedMemoryDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm_dto: SharedMemoryRingBufferDTO
    metadata_shm_dto: SharedMemoryRingBufferDTO


class RingBufferCameraSharedMemory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm: SharedMemoryRingBuffer
    metadata_shm: SharedMemoryRingBuffer
    read_only: bool

    @classmethod
    def create(
            cls,
            camera_config: CameraConfig,
            memory_allocation: int,
            read_only: bool,
    ):
        example_image = np.zeros(camera_config.image_shape, dtype=np.uint8)
        example_metadata = np.zeros(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)
        image_shm = SharedMemoryRingBuffer.create(
            example_payload=example_image,
            memory_allocation=memory_allocation,
            dtype=DEFAULT_IMAGE_DTYPE,
            read_only=read_only,
        )
        metadata_shm = SharedMemoryRingBuffer.create(
            example_payload=example_metadata,
            dtype=FRAME_METADATA_DTYPE,
            ring_buffer_length=image_shm.ring_buffer_length,
            read_only=read_only,
        )

        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )

    @classmethod
    def recreate(cls,
                dto: RingBufferCameraSharedMemoryDTO,
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

    def to_dto(self) -> RingBufferCameraSharedMemoryDTO:
        return RingBufferCameraSharedMemoryDTO(
            image_shm_dto=self.image_shm.to_dto(),
            metadata_shm_dto=self.metadata_shm.to_dto(),
        )

    def put_frame(self, image: np.ndarray, metadata: np.ndarray):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.image_shm.put_data(image)
        self.metadata_shm.put_data(metadata)
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} put frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} into shared memory"
        )

    def retrieve_latest_frame(self) -> FramePayload:
        image = self.image_shm.get_latest_payload()
        metadata = self.metadata_shm.get_latest_payload()
        metadata[FRAME_METADATA_MODEL.COPY_FROM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} retrieved frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} from shared memory"
        )
        return FramePayload.create(image=image, metadata=metadata)

    def retrieve_next_frame(self) -> FramePayload:
        image = self.image_shm.get_next_payload()
        metadata = self.metadata_shm.get_next_payload()
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
