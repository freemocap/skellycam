import logging
import multiprocessing
from dataclasses import dataclass
from typing import Optional, List

import numpy as np

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_shared_memory import ONE_GIGABYTE, \
    SharedMemoryRingBuffer, SharedMemoryRingBufferDTO
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import DEFAULT_IMAGE_DTYPE, \
    create_empty_frame_metadata, FRAME_METADATA_DTYPE
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


@dataclass
class MultiFrameEscapeSharedMemoryRingBufferDTO:
    camera_group_dto: CameraGroupDTO
    mf_metadata_shm_dto: SharedMemoryRingBufferDTO
    mf_image_shm_dto: SharedMemoryRingBufferDTO
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value


@dataclass
class MultiFrameEscapeSharedMemoryRingBuffer:
    camera_group_dto: CameraGroupDTO
    mf_metadata_shm: SharedMemoryRingBuffer
    mf_time_mapping_shm: SharedMemoryRingBuffer
    mf_image_shm: SharedMemoryRingBuffer
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value
    read_only: bool

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.camera_group_dto.camera_ids.keys())

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    @property
    def ready_to_read(self) -> bool:
        return all([camera_shared_memory.ready_to_read for camera_shared_memory in self.camera_shms.values()])

    @property
    def new_multi_frame_available(self) -> bool:
        return all([camera_shared_memory.new_frame_available for camera_shared_memory in self.camera_shms.values()])

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               read_only: bool = False):
        example_images = [np.zeros(config.image_shape, dtype=DEFAULT_IMAGE_DTYPE) for config in
                          camera_group_dto.camera_configs.values()]
        example_images_ravelled = [image.ravel() for image in example_images]
        example_mf_image_buffer = np.concatenate(
            example_images_ravelled)  # Example images unravelled into 1D arrays and concatenated

        example_mf_metadatas = [create_empty_frame_metadata(camera_id=camera_id,
                                                            frame_number=0,
                                                            config=config)
                                for camera_id, config in camera_group_dto.camera_configs.items()]
        example_mf_metadatas_ravelled = [metadata.ravel() for metadata in example_mf_metadatas]
        example_mf_metadata_buffer = np.concatenate(
            example_mf_metadatas_ravelled)  # Example metadata unravelled into 1D arrays and concatenated

        mf_image_shm = SharedMemoryRingBuffer.create(example_payload=example_mf_image_buffer,
                                                     dtype=DEFAULT_IMAGE_DTYPE,
                                                     memory_allocation=ONE_GIGABYTE)
        mf_metadata_shm = SharedMemoryRingBuffer.create(example_payload=example_mf_metadata_buffer,
                                                        dtype=FRAME_METADATA_DTYPE,
                                                        memory_allocation=ONE_GIGABYTE)
        return cls(camera_group_dto=camera_group_dto,
                   mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   shm_valid_flag=multiprocessing.Value('b', True),
                   latest_mf_number=multiprocessing.Value("l", -1),
                   read_only=read_only)

    @classmethod
    def recreate(cls,
                 camera_group_dto: CameraGroupDTO,
                 shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO,
                 read_only: bool):
        mf_image_shm = SharedMemoryRingBuffer.recreate(dto=shm_dto.mf_image_shm_dto,
                                                       read_only=read_only)
        mf_metadata_shm = SharedMemoryRingBuffer.recreate(dto=shm_dto.mf_metadata_shm_dto,
                                                          read_only=read_only)

        return cls(camera_group_dto=camera_group_dto,
                   mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,

                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_mf_number=shm_dto.latest_mf_number,
                   read_only=read_only)

    def to_dto(self) -> MultiFrameEscapeSharedMemoryRingBufferDTO:
        return MultiFrameEscapeSharedMemoryRingBufferDTO(camera_group_dto=self.camera_group_dto,
                                                         mf_metadata_shm_dto=self.mf_metadata_shm.to_dto(),
                                                         mf_image_shm_dto=self.mf_image_shm.to_dto(),
                                                         shm_valid_flag=self.shm_valid_flag,
                                                         latest_mf_number=self.latest_mf_number, )

    def put_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        for camera_id, camera_shared_memory in self.camera_shms.items():
            camera_shared_memory.put_frame(**multi_frame_payload.get_frame(camera_id).model_dump())

    def get_latest_multi_frame_payload(self,
                                       previous_payload: Optional[MultiFramePayload],
                                       camera_configs: CameraConfigs,
                                       ) -> MultiFramePayload:
        with self.lock:
            if previous_payload is None:
                mf_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_configs=camera_configs)
            else:
                mf_payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                                camera_configs=camera_configs)

            if not self.valid:
                raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

            for camera_id, camera_shared_memory in self.camera_shms.items():
                frame = camera_shared_memory.retrieve_latest_frame()
                mf_payload.add_frame(frame)
            if not mf_payload or not mf_payload.full:
                raise ValueError("Did not read full multi-frame mf_payload!")
            return mf_payload

    def get_next_multi_frame_payload(self,
                                     previous_payload: Optional[MultiFramePayload],
                                     camera_configs: CameraConfigs,
                                     ) -> MultiFramePayload:
        with self.lock:
            if self.read_only:
                raise ValueError("Cannot read `next` from shared memory that is read-only, use `get_latest..` instead!")
            if previous_payload is None:
                mf_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_configs=camera_configs)
            else:
                mf_payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                                camera_configs=camera_configs)

            if not self.valid:
                raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

            for camera_id, camera_shared_memory in self.camera_shms.items():
                frame = camera_shared_memory.retrieve_next_frame()
                mf_payload.add_frame(frame)
            if not mf_payload or not mf_payload.full:
                raise ValueError("Did not read full multi-frame mf_payload!")
            if not mf_payload.multi_frame_number == self.latest_mf_number.value + 1:
                raise ValueError(
                    f"Multi-frame number mismatch! Expected {self.latest_mf_number.value + 1}, got {mf_payload.multi_frame_number}")
            self.latest_mf_number.value = mf_payload.multi_frame_number
            return mf_payload

    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it        
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        self.shm_valid_flag.value = False
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
