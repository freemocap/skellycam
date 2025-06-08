import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, DEFAULT_IMAGE_DTYPE, create_empty_frame_metadata
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload, MultiFrameNumpyBuffer
from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement, SharedMemoryElementDTO
from skellycam.core.types import CameraGroupIdString

logger = logging.getLogger(__name__)


@dataclass
class MultiframePayloadSingleSlotSharedMemoryDTO:
    camera_group_id: CameraGroupIdString

    mf_time_mapping_shm_dto: SharedMemoryElementDTO
    mf_metadata_shm_dto: SharedMemoryElementDTO
    mf_image_shm_dto: SharedMemoryElementDTO
    shm_valid_flag: multiprocessing.Value
    latest_written_mf_number: multiprocessing.Value
    latest_read_mf_number: multiprocessing.Value


@dataclass
class MultiframePayloadSingleSlotSharedMemory:
    camera_group_id: CameraGroupIdString
    mf_time_mapping_shm: SharedMemoryElement
    mf_metadata_shm: SharedMemoryElement
    mf_image_shm: SharedMemoryElement

    shm_valid_flag: multiprocessing.Value
    latest_written_mf_number: multiprocessing.Value
    latest_read_mf_number: multiprocessing.Value

    read_only: bool

    previous_read_mf_payload: MultiFramePayload | None = None

    @classmethod
    def create_from_configs(cls,
                            camera_group_id: CameraGroupIdString,
                            configs: CameraConfigs,
                            read_only: bool = False):
        example_images = [np.zeros(config.image_shape, dtype=DEFAULT_IMAGE_DTYPE) for config in
                          configs.values()]
        example_images_ravelled = [image.ravel() for image in example_images]
        example_mf_image_buffer = np.concatenate(
            example_images_ravelled)  # Example images unravelled into 1D arrays and concatenated

        example_mf_metadatas = [create_empty_frame_metadata(frame_number=0,
                                                            config=config)
                                for camera_id, config in configs.items()]
        example_mf_metadatas_ravelled = [metadata.ravel() for metadata in example_mf_metadatas]
        example_mf_metadata_buffer = np.concatenate(
            example_mf_metadatas_ravelled)  # Example metadata unravelled into 1D arrays and concatenated

        mf_image_shm = SharedMemoryElement.create(shape=example_mf_image_buffer.shape,
                                                  dtype=DEFAULT_IMAGE_DTYPE)
        mf_metadata_shm = SharedMemoryElement.create(shape=example_mf_metadata_buffer.shape,
                                                     dtype=FRAME_METADATA_DTYPE)
        mf_time_mapping_shm = SharedMemoryElement.create(shape=np.zeros(2, dtype=np.int64).shape,
                                                         dtype=np.int64)
        return cls(mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   shm_valid_flag=multiprocessing.Value('b', True),
                   latest_written_mf_number=multiprocessing.Value("l", -1),
                   latest_read_mf_number=multiprocessing.Value("l", -1),
                     camera_group_id=camera_group_id,
                   read_only=read_only)

    @classmethod
    def recreate(cls,
                 shm_dto: MultiframePayloadSingleSlotSharedMemoryDTO,
                 read_only: bool):
        mf_image_shm = SharedMemoryElement.recreate_from_dto(dto=shm_dto.mf_image_shm_dto)
        mf_metadata_shm = SharedMemoryElement.recreate_from_dto(dto=shm_dto.mf_metadata_shm_dto)
        mf_time_mapping_shm = SharedMemoryElement.recreate_from_dto(dto=shm_dto.mf_time_mapping_shm_dto)

        return cls(mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_written_mf_number=shm_dto.latest_written_mf_number,
                   latest_read_mf_number=multiprocessing.Value("l", -1),
                     camera_group_id=shm_dto.camera_group_id,
                   read_only=read_only)

    @property
    def first_frame_written(self) -> bool:
        return self.latest_written_mf_number.value >= 0 and self.shm_valid_flag.value

    def to_dto(self) -> MultiframePayloadSingleSlotSharedMemoryDTO:
        return MultiframePayloadSingleSlotSharedMemoryDTO(mf_time_mapping_shm_dto=self.mf_time_mapping_shm.to_dto(),
                                                          mf_metadata_shm_dto=self.mf_metadata_shm.to_dto(),
                                                          mf_image_shm_dto=self.mf_image_shm.to_dto(),
                                                          shm_valid_flag=self.shm_valid_flag,
                                                          latest_written_mf_number=self.latest_written_mf_number,
                                                            camera_group_id=self.camera_group_id,
                                                          latest_read_mf_number=self.latest_read_mf_number)

    def put_multiframe(self,
                       mf_payload: MultiFramePayload,
                       overwrite: bool) -> None:
        if not self.shm_valid_flag.value:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        if not mf_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")
        if self.read_only:
            raise ValueError("Cannot write to read-only shared memory!")

        if mf_payload.multi_frame_number <= self.latest_written_mf_number.value:
            raise ValueError(
                f"Cannot write multi-frame payload with number {mf_payload.multi_frame_number} to shared memory, "
                f"as it is not newer than the latest written multi-frame number {self.latest_written_mf_number.value}!")
        if mf_payload.multi_frame_number <= self.latest_read_mf_number.value:
            if not overwrite:
                raise ValueError(
                    f"Cannot write multi-frame payload with number {mf_payload.multi_frame_number} to shared memory, "
                    f"as it is not newer than the latest read multi-frame number {self.latest_read_mf_number.value}!")
            logger.warning(
                f"FYI - Writing multi-frame payload with number {mf_payload.multi_frame_number} to shared memory before previous mf was read. ")
        for frame in mf_payload.frames.values():
            frame.metadata[
                FRAME_METADATA_MODEL.COPY_TO_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()

        mf_numpy_buffer: MultiFrameNumpyBuffer = mf_payload.to_numpy_buffer()

        self.mf_image_shm.put_data(mf_numpy_buffer.mf_image_buffer)

        self.mf_metadata_shm.put_data(mf_numpy_buffer.mf_metadata_buffer)

        self.mf_time_mapping_shm.put_data(mf_numpy_buffer.mf_time_mapping_buffer)

        self.latest_written_mf_number.value = mf_payload.multi_frame_number

    def retrieve_multiframe(self, camera_configs: CameraConfigs) -> MultiFramePayload:

        if not self.shm_valid_flag.value:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        mf_payload = MultiFramePayload.from_numpy_buffer(
            buffer=MultiFrameNumpyBuffer.from_buffers(mf_image_buffer=self.mf_image_shm.get_data(),
                                                      mf_metadata_buffer=self.mf_metadata_shm.get_data(),
                                                      mf_time_mapping_buffer=self.mf_time_mapping_shm.get_data(),
                                                      ),
            camera_configs=camera_configs,
            camera_group_id=self.camera_group_id,
        )
        self.latest_read_mf_number.value = mf_payload.multi_frame_number
        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")

        for frame in mf_payload.frames.values():
            frame.metadata[
                FRAME_METADATA_MODEL.COPY_FROM_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()

        return mf_payload

    def close(self):
        self.mf_image_shm.close()
        self.mf_metadata_shm.close()
        self.mf_time_mapping_shm.close()

    def unlink(self):
        self.mf_image_shm.unlink()
        self.mf_metadata_shm.unlink()
        self.mf_time_mapping_shm.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
