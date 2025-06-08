import logging
import multiprocessing
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import DEFAULT_IMAGE_DTYPE, \
    create_empty_frame_metadata, FRAME_METADATA_DTYPE, FRAME_METADATA_MODEL
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload, MultiFrameNumpyBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import ONE_GIGABYTE, \
    SharedMemoryRingBuffer, SharedMemoryRingBufferDTO
from skellycam.core.types import CameraGroupIdString

logger = logging.getLogger(__name__)


@dataclass
class MultiFrameSharedMemoryRingBufferDTO:
    camera_group_id: CameraGroupIdString
    mf_time_mapping_shm_dto: SharedMemoryRingBufferDTO
    mf_metadata_shm_dto: SharedMemoryRingBufferDTO
    mf_image_shm_dto: SharedMemoryRingBufferDTO
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value


@dataclass
class MultiFrameSharedMemoryRingBuffer:
    camera_group_id: CameraGroupIdString
    mf_time_mapping_shm: SharedMemoryRingBuffer
    mf_metadata_shm: SharedMemoryRingBuffer
    mf_image_shm: SharedMemoryRingBuffer

    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value

    read_only: bool

    previous_read_mf_payload: MultiFramePayload | None = None

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    @property
    def first_frame_written(self) -> bool:
        return all([self.mf_metadata_shm.first_frame_written,
                    self.mf_image_shm.first_frame_written,
                    self.mf_time_mapping_shm.first_frame_written])

    @property
    def new_multi_frame_available(self) -> bool:
        return all([self.mf_metadata_shm.new_data_available,
                    self.mf_image_shm.new_data_available,
                    self.mf_time_mapping_shm.new_data_available])

    @classmethod
    def create_from_configs(cls,
                            configs: CameraConfigs,
                            camera_group_id: CameraGroupIdString,
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

        mf_image_shm = SharedMemoryRingBuffer.create(example_payload=example_mf_image_buffer,
                                                     dtype=DEFAULT_IMAGE_DTYPE,
                                                     memory_allocation=ONE_GIGABYTE,
                                                     read_only=read_only)
        mf_metadata_shm = SharedMemoryRingBuffer.create(example_payload=example_mf_metadata_buffer,
                                                        dtype=FRAME_METADATA_DTYPE,
                                                        ring_buffer_length=mf_image_shm.ring_buffer_length,
                                                        read_only=read_only)
        mf_time_mapping_shm = SharedMemoryRingBuffer.create(example_payload=np.zeros(2, dtype=np.int64),
                                                            dtype=np.int64,
                                                            ring_buffer_length=mf_image_shm.ring_buffer_length,
                                                            read_only=read_only)
        return cls(mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   shm_valid_flag=multiprocessing.Value('b', True),
                   latest_mf_number=multiprocessing.Value("l", -1),
                   camera_group_id=camera_group_id,
                   read_only=read_only)

    @classmethod
    def recreate(cls,
                 shm_dto: MultiFrameSharedMemoryRingBufferDTO,
                 read_only: bool):
        mf_image_shm = SharedMemoryRingBuffer.recreate(dto=shm_dto.mf_image_shm_dto,
                                                       read_only=read_only)
        mf_metadata_shm = SharedMemoryRingBuffer.recreate(dto=shm_dto.mf_metadata_shm_dto,
                                                          read_only=read_only)
        mf_time_mapping_shm = SharedMemoryRingBuffer.recreate(dto=shm_dto.mf_time_mapping_shm_dto,
                                                              read_only=read_only)

        return cls(mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_mf_number=shm_dto.latest_mf_number,
                   camera_group_id=shm_dto.camera_group_id,
                   read_only=read_only)

    def to_dto(self) -> MultiFrameSharedMemoryRingBufferDTO:
        return MultiFrameSharedMemoryRingBufferDTO(mf_time_mapping_shm_dto=self.mf_time_mapping_shm.to_dto(),
                                                   mf_metadata_shm_dto=self.mf_metadata_shm.to_dto(),
                                                   mf_image_shm_dto=self.mf_image_shm.to_dto(),
                                                   shm_valid_flag=self.shm_valid_flag,
                                                   latest_mf_number=self.latest_mf_number,
                                                   camera_group_id=self.camera_group_id,)

    def put_multiframe(self,
                       mf_payload: MultiFramePayload, overwrite: bool) -> None:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        if not mf_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")
        if self.read_only:
            raise ValueError("Cannot write to read-only shared memory!")

        for frame in mf_payload.frames.values():
            frame.metadata[
                FRAME_METADATA_MODEL.COPY_TO_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()

        mf_numpy_buffer: MultiFrameNumpyBuffer = mf_payload.to_numpy_buffer()

        self.mf_image_shm.put_data(mf_numpy_buffer.mf_image_buffer, overwrite=overwrite)

        self.mf_metadata_shm.put_data(mf_numpy_buffer.mf_metadata_buffer, overwrite=overwrite)

        self.mf_time_mapping_shm.put_data(mf_numpy_buffer.mf_time_mapping_buffer, overwrite=overwrite)

        if not {self.mf_image_shm.last_written_index.value,
                self.mf_metadata_shm.last_written_index.value,
                self.mf_time_mapping_shm.last_written_index.value,
                mf_payload.multi_frame_number} == {mf_payload.multi_frame_number}:
            raise ValueError("Multi-frame number mismatch! "
                             f"Image: {self.mf_image_shm.last_written_index.value}, "
                             f"Metadata: {self.mf_metadata_shm.last_written_index.value}, "
                             f"Time Mapping: {self.mf_time_mapping_shm.last_written_index.value}, "
                             f"Expected: {mf_payload.multi_frame_number}")

        self.latest_mf_number.value = mf_payload.multi_frame_number

    def get_latest_multiframe(self,
                              camera_configs: CameraConfigs,
                              ) -> MultiFramePayload:

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        mf_payload = MultiFramePayload.from_numpy_buffer(
            buffer=MultiFrameNumpyBuffer.from_buffers(mf_image_buffer=self.mf_image_shm.get_latest_payload(),
                                                      mf_metadata_buffer=self.mf_metadata_shm.get_latest_payload(),
                                                      mf_time_mapping_buffer=self.mf_time_mapping_shm.get_latest_payload(),
                                                      ),
            camera_configs=camera_configs,
            camera_group_id=self.camera_group_id)

        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        for frame in mf_payload.frames.values():
            frame.metadata[
                FRAME_METADATA_MODEL.COPY_FROM_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()

        return mf_payload

    def get_next_multiframe(self,
                            camera_configs: CameraConfigs,
                            ) -> MultiFramePayload:
        if self.read_only:
            raise ValueError(
                "Cannot retrieve `next` multi-frame payload from read-only shared memory (bc it increments the counter), use 'latest' instead")

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        mf_payload = MultiFramePayload.from_numpy_buffer(
            buffer=MultiFrameNumpyBuffer.from_buffers(mf_image_buffer=self.mf_image_shm.get_next_payload(),
                                                      mf_metadata_buffer=self.mf_metadata_shm.get_next_payload(),
                                                      mf_time_mapping_buffer=self.mf_time_mapping_shm.get_next_payload(),
                                                      ),
            camera_group_id=self.camera_group_id,
            camera_configs=camera_configs)

        if (not self.previous_read_mf_payload and mf_payload.multi_frame_number != 0) or \
                (
                        self.previous_read_mf_payload and mf_payload.multi_frame_number != self.previous_read_mf_payload.multi_frame_number + 1):
            raise ValueError(
                f"Multi-frame number mismatch! Expected {self.latest_mf_number.value}, got {mf_payload.multi_frame_number}")
        self.previous_read_mf_payload = mf_payload

        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        for frame in mf_payload.frames.values():
            frame.metadata[
                FRAME_METADATA_MODEL.COPY_FROM_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()

        return mf_payload

    def get_all_new_multiframes(self,
                                camera_configs: CameraConfigs,
                                ) -> list[MultiFramePayload]:
        """
        Retrieves all new multi-frames from the shared memory.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        mfs: list[MultiFramePayload] = []
        while self.new_multi_frame_available:
            mf_payload = self.get_next_multiframe(camera_configs=camera_configs)
            mfs.append(mf_payload)

        return mfs

    def close(self):
        self.mf_image_shm.close()
        self.mf_metadata_shm.close()
        self.mf_time_mapping_shm.close()

    def unlink(self):
        self.mf_image_shm.unlink()
        self.mf_metadata_shm.unlink()
        self.mf_time_mapping_shm.unlink()
        self.shm_valid_flag.value = False

    def close_and_unlink(self):
        self.close()
        self.unlink()
