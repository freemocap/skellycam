import logging
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import DEFAULT_IMAGE_DTYPE, \
    create_empty_frame_metadata, FRAME_METADATA_DTYPE, FRAME_METADATA_MODEL
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload, MultiFrameNumpyBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import ONE_GIGABYTE, \
    SharedMemoryRingBuffer, SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber, SharedMemoryNumberDTO
from skellycam.core.types import CameraGroupIdString

logger = logging.getLogger(__name__)


@dataclass
class MultiFrameSharedMemoryRingBufferDTO:
    camera_group_id: CameraGroupIdString
    mf_time_mapping_shm_dto: SharedMemoryRingBufferDTO
    mf_metadata_shm_dto: SharedMemoryRingBufferDTO
    mf_image_shm_dto: SharedMemoryRingBufferDTO
    latest_mf_number_shm_dto: SharedMemoryNumberDTO


@dataclass
class MultiFrameSharedMemoryRingBuffer:
    camera_group_id: CameraGroupIdString
    mf_time_mapping_shm: SharedMemoryRingBuffer
    mf_metadata_shm: SharedMemoryRingBuffer
    mf_image_shm: SharedMemoryRingBuffer
    latest_mf_number: SharedMemoryNumber

    read_only: bool
    original: bool = False
    latest_mf: MultiFramePayload | None = None

    @property
    def valid(self) -> bool:
        return all([self.mf_time_mapping_shm.valid,
                    self.mf_metadata_shm.valid,
                    self.mf_image_shm.valid,
                    self.latest_mf_number.valid])

    @valid.setter
    def valid(self, value: bool):
        self.mf_time_mapping_shm.valid = value
        self.mf_metadata_shm.valid = value
        self.mf_image_shm.valid = value
        self.latest_mf_number.valid = value

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
        latest_mf_number = SharedMemoryNumber.create(initial_value=-1)
        return cls(mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   camera_group_id=camera_group_id,
                   latest_mf_number=SharedMemoryNumber.create(initial_value=-1),
                   read_only=read_only,
                   original=True)

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
        latest_mf_number = SharedMemoryNumber.recreate(dto=shm_dto.latest_mf_number_shm_dto)
        return cls(mf_image_shm=mf_image_shm,
                   mf_metadata_shm=mf_metadata_shm,
                   mf_time_mapping_shm=mf_time_mapping_shm,
                   camera_group_id=shm_dto.camera_group_id,
                   latest_mf_number=latest_mf_number,
                   read_only=read_only,
                   original=False)

    def to_dto(self) -> MultiFrameSharedMemoryRingBufferDTO:
        return MultiFrameSharedMemoryRingBufferDTO(mf_time_mapping_shm_dto=self.mf_time_mapping_shm.to_dto(),
                                                   mf_metadata_shm_dto=self.mf_metadata_shm.to_dto(),
                                                   mf_image_shm_dto=self.mf_image_shm.to_dto(),
                                                   latest_mf_number_shm_dto=self.latest_mf_number.to_dto(),
                                                   camera_group_id=self.camera_group_id, )

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

        mf = MultiFramePayload.from_numpy_buffer(
            buffer=MultiFrameNumpyBuffer.from_buffers(mf_image_buffer=self.mf_image_shm.get_next_payload(),
                                                      mf_metadata_buffer=self.mf_metadata_shm.get_next_payload(),
                                                      mf_time_mapping_buffer=self.mf_time_mapping_shm.get_next_payload(),
                                                      ),
            camera_group_id=self.camera_group_id,
            camera_configs=camera_configs)

        self._validate_mf(mf)
        for frame in mf.frames.values():
            frame.metadata[
                FRAME_METADATA_MODEL.COPY_FROM_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS.value] = time.perf_counter_ns()
        self.latest_mf = mf
        return mf

    def _validate_mf(self, mf: MultiFramePayload, strict_mode: bool = False):
        if not isinstance(mf, MultiFramePayload):
            raise TypeError(f"Expected MultiFramePayload, got {type(mf)}")
        if (not self.latest_mf and mf.multi_frame_number != 0):
            raise ValueError(
                f"Initial multi-frame number mismatch! Expected multiframe_number = 0, got {mf.multi_frame_number}")

        if (self.latest_mf and mf.multi_frame_number != self.latest_mf.multi_frame_number + 1):
            msg = f"Multi-frame number mismatch! Expected {self.latest_mf_number.value}, got {mf.multi_frame_number}"
            if strict_mode:
                raise ValueError(msg)
            else:
                logger.warning(msg)

        if not mf or not mf.full:
            raise ValueError("Did not read full multi-frame mf!")

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
        if self.read_only:
            raise ValueError("Cannot unlink read-only shared memory!")
        if not self.original:
            raise ValueError("Cannot unlink shared memory that is not original!")
        self.valid = False
        self.mf_image_shm.unlink()
        self.mf_metadata_shm.unlink()
        self.mf_time_mapping_shm.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
