import logging
import time
from typing import Dict

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_element import SharedMemoryElement
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_ring_buffer import SharedMemoryRingBuffer, \
    SharedMemoryRingBufferDTO
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, FRAME_METADATA_SHAPE, DEFAULT_IMAGE_DTYPE

logger = logging.getLogger(__name__)


class CameraSharedMemoryDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm_dto: SharedMemoryRingBufferDTO
    metadata_shm_dto: SharedMemoryRingBufferDTO


CameraSharedMemoryDTOs = Dict[CameraId, CameraSharedMemoryDTO]


class CameraSharedMemory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_shm: SharedMemoryRingBuffer
    metadata_shm: SharedMemoryRingBuffer
    read_only: bool

    @classmethod
    def create(
            cls,
            camera_config: CameraConfig,
            read_only: bool,
    ):
        example_image = np.zeros(camera_config.image_shape, dtype=DEFAULT_IMAGE_DTYPE)
        example_metadata = np.zeros(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)

        image_shm = SharedMemoryRingBuffer.create(
            example_payload=example_image,
            dtype=DEFAULT_IMAGE_DTYPE,
        )
        metadata_shm = SharedMemoryRingBuffer.create(
            example_payload=example_metadata,
            dtype=FRAME_METADATA_DTYPE,
            ring_buffer_length=image_shm.ring_buffer_length,
        )

        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )

    @classmethod
    def recreate(cls,
                 dto: CameraSharedMemoryDTO,
                 read_only: bool, ):
        image_shm = SharedMemoryRingBuffer.recreate(
            dto=dto.image_shm_dto
        )
        metadata_shm = SharedMemoryRingBuffer.recreate(
            dto= dto.metadata_shm_dto,
        )
        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            read_only=read_only,
        )


    def to_dto(self) -> CameraSharedMemoryDTO:
        return CameraSharedMemoryDTO(image_shm_dto=self.image_shm.to_dto(),
                                     metadata_shm_dto=self.metadata_shm.to_dto())

    def put_new_frame(self, image: np.ndarray, metadata: np.ndarray):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.image_shm.put_payload(image)
        self.metadata_shm.put_payload(metadata)
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} put frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} into shared memory"
        )

    def retrieve_next_frame(self) -> FramePayload:
        """
        Always get the NEXT frame, based on the last read frame (cannot be called from read-only instances because it increments the 'last_read_index' of the ring buffer)
        :return:
        """
        if self.read_only:
            raise ValueError("Cannot retrieve frame from read-only instance of shared memory. Use `retrieve`_latest_frame` instead.")
        image = self.image_shm.get_next_payload()
        metadata = self.metadata_shm.get_next_payload()
        metadata[FRAME_METADATA_MODEL.COPY_FROM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        logger.loop(
            f"Camera {metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]} retrieved frame#{metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} from shared memory"
        )
        return FramePayload.create(image=image, metadata=metadata)

    def retrieve_latest_frame(self) -> FramePayload:
        """
        Gets the most recent frame, but not necessarily the next frame afte the previous one that was retrieved
        (Good for showing up-to-date images without lag, but may skip frames)
        :return:
        """
        image = self.image_shm.get_latest_payload()
        metadata = self.metadata_shm.get_latest_payload()
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
