import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.shmorchestrator.shared_memory.shared_memory_element import SharedMemoryElement
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, FRAME_METADATA_SHAPE, DEFAULT_IMAGE_DTYPE

logger = logging.getLogger(__name__)


@dataclass
class CameraSharedMemoryDTO:
    last_read_frame_number: multiprocessing.Value
    last_written_frame_number: multiprocessing.Value
    image_shm_name: str
    metadata_shm_name: str

@dataclass
class SingleSlotCameraSharedMemory:
    last_read_frame_number: multiprocessing.Value
    last_written_frame_number: multiprocessing.Value
    image_shm: SharedMemoryElement
    metadata_shm: SharedMemoryElement
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
            last_read_frame_number=multiprocessing.Value("l", -1),
            last_written_frame_number=multiprocessing.Value("l", -1),
            read_only=read_only,

        )

    @classmethod
    def recreate(cls,
                 camera_config: CameraConfig,
                 camera_shm_dto: CameraSharedMemoryDTO,
                 read_only: bool, ):
        image_shm = SharedMemoryElement.recreate(
            camera_shm_dto.image_shm_name,
            shape=camera_config.image_shape,
            dtype=np.uint8,
        )
        metadata_shm = SharedMemoryElement.recreate(
            camera_shm_dto.metadata_shm_name,
            shape=FRAME_METADATA_SHAPE,
            dtype=FRAME_METADATA_DTYPE,
        )
        return cls(
            image_shm=image_shm,
            metadata_shm=metadata_shm,
            last_read_frame_number=camera_shm_dto.last_read_frame_number,
            last_written_frame_number=camera_shm_dto.last_written_frame_number,
            read_only=read_only,
        )

    def to_dto(self) -> CameraSharedMemoryDTO:
        return CameraSharedMemoryDTO(image_shm_name=self.image_shm.name,
                                     metadata_shm_name=self.metadata_shm.name,
                                     last_written_frame_number=self.last_written_frame_number,
                                     last_read_frame_number=self.last_read_frame_number)

    @property
    def new_frame_available(self) -> bool:
        return self.last_read_frame_number.value < self.last_written_frame_number.value

    def put_frame(self, image: np.ndarray, metadata: np.ndarray):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.image_shm.put_data(image)
        self.metadata_shm.put_data(metadata)
        self.last_written_frame_number.value = metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]
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
        self.last_read_frame_number.value = metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]
        return FramePayload.create(image=image, metadata=metadata)

    def close(self):
        self.image_shm.close()
        self.metadata_shm.close()

    def unlink(self):
        self.image_shm.unlink()
        self.metadata_shm.unlink()
