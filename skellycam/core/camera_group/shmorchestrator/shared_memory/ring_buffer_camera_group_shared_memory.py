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
    mf_time_mapping_shm_dto: SharedMemoryRingBufferDTO
    mf_metadata_shm_dto: SharedMemoryRingBufferDTO
    mf_image_shm_dto: SharedMemoryRingBufferDTO
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value


@dataclass
class MultiFrameEscapeSharedMemoryRingBuffer:
    camera_group_dto: CameraGroupDTO

    mf_time_mapping_shm: SharedMemoryRingBuffer
    mf_metadata_shm: SharedMemoryRingBuffer
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
                                                        ring_buffer_length=mf_image_shm.ring_buffer_length,
                                                        )
        mf_time_mapping_shm = SharedMemoryRingBuffer.create(example_payload=np.zeros(2, dtype=np.int64),
                                                            dtype=np.int64,
                                                            ring_buffer_length=mf_image_shm.ring_buffer_length,
                                                            )
        return cls(camera_group_dto=camera_group_dto,
                   mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
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
        mf_time_mapping_shm = SharedMemoryRingBuffer.recreate(dto=shm_dto.mf_time_mapping_shm_dto,
                                                              read_only=read_only)

        return cls(camera_group_dto=camera_group_dto,
                   mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_mf_number=shm_dto.latest_mf_number,
                   read_only=read_only)

    def to_dto(self) -> MultiFrameEscapeSharedMemoryRingBufferDTO:
        return MultiFrameEscapeSharedMemoryRingBufferDTO(camera_group_dto=self.camera_group_dto,
                                                         mf_time_mapping_shm_dto=self.mf_time_mapping_shm.to_dto(),
                                                         mf_metadata_shm_dto=self.mf_metadata_shm.to_dto(),
                                                         mf_image_shm_dto=self.mf_image_shm.to_dto(),
                                                         shm_valid_flag=self.shm_valid_flag,
                                                         latest_mf_number=self.latest_mf_number, )

    def put_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        if not multi_frame_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")
        mf_numpy_buffer = multi_frame_payload.to_numpy_buffer()
        self.mf_image_shm.put_data(mf_numpy_buffer.mf_image_buffer)
        self.mf_metadata_shm.put_data(mf_numpy_buffer.mf_metadata_buffer)
        self.mf_time_mapping_shm.put_data(mf_numpy_buffer.mf_time_mapping_buffer)
        if not {self.mf_image_shm.last_written_index.value,
                self.mf_metadata_shm.last_written_index.value,
                self.mf_time_mapping_shm.last_written_index.value,
                multi_frame_payload.multi_frame_number} == {multi_frame_payload.multi_frame_number}:
            raise ValueError("Multi-frame number mismatch! "
                             f"Image: {self.mf_image_shm.last_written_index.value}, "
                             f"Metadata: {self.mf_metadata_shm.last_written_index.value}, "
                             f"Time Mapping: {self.mf_time_mapping_shm.last_written_index.value}, "
                             f"Expected: {multi_frame_payload.multi_frame_number}")

        self.latest_mf_number.value = multi_frame_payload.multi_frame_number


    def get_multi_frame_payload(self,
                                     previous_payload: Optional[MultiFramePayload],
                                     camera_configs: CameraConfigs,
                                     ) -> MultiFramePayload:
        if previous_payload is None:
            mf_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_configs=camera_configs)
        else:
            mf_payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                            camera_configs=camera_configs)

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        mf_image_buffer = self.mf_image_shm.get_data()
        mf_metadata_buffer = self.mf_metadata_shm.get_data()
        mf_time_mapping_buffer = self.mf_time_mapping_shm.get_data()

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
