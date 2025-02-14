import logging
import multiprocessing
import time
from dataclasses import dataclass
from typing import List, Literal, Optional

import numpy as np

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_shared_memory import ONE_GIGABYTE, \
    SharedMemoryRingBuffer, SharedMemoryRingBufferDTO
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import DEFAULT_IMAGE_DTYPE, \
    create_empty_frame_metadata, FRAME_METADATA_DTYPE
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFrameNumpyBuffer
from skellycam.core.playback.video_group_dto import VideoGroupDTO

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
    camera_group_dto: CameraGroupDTO | VideoGroupDTO

    mf_time_mapping_shm: SharedMemoryRingBuffer
    mf_metadata_shm: SharedMemoryRingBuffer
    mf_image_shm: SharedMemoryRingBuffer

    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value

    read_only: bool

    previous_read_mf_payload: Optional[MultiFramePayload] = None

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.camera_group_dto.camera_ids.keys())

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    @property
    def ready_to_read(self) -> bool:
        return all([self.mf_metadata_shm.ready_to_read,
                    self.mf_image_shm.ready_to_read,
                    self.mf_time_mapping_shm.ready_to_read])

    @property
    def new_multi_frame_available(self) -> bool:
        return all([self.mf_metadata_shm.new_data_available,
                    self.mf_image_shm.new_data_available,
                    self.mf_time_mapping_shm.new_data_available])

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
                                                     memory_allocation=ONE_GIGABYTE*int(len(list(camera_group_dto.camera_configs.keys()))),
                                                     read_only=read_only)
        mf_metadata_shm = SharedMemoryRingBuffer.create(example_payload=example_mf_metadata_buffer,
                                                        dtype=FRAME_METADATA_DTYPE,
                                                        ring_buffer_length=mf_image_shm.ring_buffer_length,
                                                        read_only=read_only)
        mf_time_mapping_shm = SharedMemoryRingBuffer.create(example_payload=np.zeros(2, dtype=np.int64),
                                                            dtype=np.int64,
                                                            ring_buffer_length=mf_image_shm.ring_buffer_length,
                                                            read_only=read_only)
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

    def put_multi_frame_payload(self,
                                multi_frame_payload: MultiFramePayload):
        tik = time.perf_counter_ns()
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        if not multi_frame_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")
        if self.read_only:
            raise ValueError("Cannot write to read-only shared memory!")
        tik_check = time.perf_counter_ns()
        mf_numpy_buffer: MultiFrameNumpyBuffer = multi_frame_payload.to_numpy_buffer()
        tik_to_numpy = time.perf_counter_ns()
        self.mf_image_shm.put_data(mf_numpy_buffer.mf_image_buffer)
        tik_put_image = time.perf_counter_ns()
        self.mf_metadata_shm.put_data(mf_numpy_buffer.mf_metadata_buffer)
        tik_put_metadata = time.perf_counter_ns()
        self.mf_time_mapping_shm.put_data(mf_numpy_buffer.mf_time_mapping_buffer)
        tik_put_time_mapping = time.perf_counter_ns()

        if not {self.mf_image_shm.last_written_index.value,
                self.mf_metadata_shm.last_written_index.value,
                self.mf_time_mapping_shm.last_written_index.value,
                multi_frame_payload.multi_frame_number} == {multi_frame_payload.multi_frame_number}:
            self.camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            raise ValueError("Multi-frame number mismatch! "
                             f"Image: {self.mf_image_shm.last_written_index.value}, "
                             f"Metadata: {self.mf_metadata_shm.last_written_index.value}, "
                             f"Time Mapping: {self.mf_time_mapping_shm.last_written_index.value}, "
                             f"Expected: {multi_frame_payload.multi_frame_number}")

        self.latest_mf_number.value = multi_frame_payload.multi_frame_number
        tok = time.perf_counter_ns()
        # if multi_frame_payload.multi_frame_number % 10 == 0:
        #     print(f"\tPUT MF IN SHM -  multi-frame {multi_frame_payload.multi_frame_number} to shared memory (took: {(tok - tik)/1e6:.3f}ms total, "
        #             f"\n\t\tconvert to numpy buffer: {(tik_to_numpy - tik_check)/1e6:.3f}ms, "
        #             f"\n\t\tput image in shm : {(tik_put_image - tik_to_numpy)/1e6:.3f}ms, "
        #             f"\n\t\tput metadata in shm: {(tik_put_metadata - tik_put_image)/1e6:.3f}ms, "
        #             f"\n\t\tput time mapping in shm: {(tik_put_time_mapping - tik_put_metadata)/1e6:.3f}ms)")

    def get_multi_frame_payload(self,
                                camera_configs: CameraConfigs,
                                retrieve_type: Literal["latest", "next"]
                                ) -> MultiFramePayload:
        if retrieve_type == "next" and self.read_only:
            raise ValueError(
                "Cannot retrieve `next` multi-frame payload from read-only shared memory (bc it increments the counter), use 'latest' instead")

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        if retrieve_type == "next":
            tik = time.perf_counter_ns()
            mf_payload = MultiFramePayload.from_numpy_buffer(
                buffer=MultiFrameNumpyBuffer.from_buffers(mf_image_buffer=self.mf_image_shm.get_next_payload(),
                                                          mf_metadata_buffer=self.mf_metadata_shm.get_next_payload(),
                                                          mf_time_mapping_buffer=self.mf_time_mapping_shm.get_next_payload(),
                                                          ),
                camera_configs=camera_configs)
            tik_from_numpy = time.perf_counter_ns()
            if (not self.previous_read_mf_payload and mf_payload.multi_frame_number != 0) or \
                    (self.previous_read_mf_payload and mf_payload.multi_frame_number != self.previous_read_mf_payload.multi_frame_number + 1):
                raise ValueError(
                    f"Multi-frame number mismatch! Expected {self.latest_mf_number.value}, got {mf_payload.multi_frame_number}")
            self.previous_read_mf_payload = mf_payload
            tok = time.perf_counter_ns()
        elif retrieve_type == "latest":
            mf_payload = MultiFramePayload.from_numpy_buffer(
                buffer=MultiFrameNumpyBuffer.from_buffers(mf_image_buffer=self.mf_image_shm.get_latest_payload(),
                                                          mf_metadata_buffer=self.mf_metadata_shm.get_latest_payload(),
                                                          mf_time_mapping_buffer=self.mf_time_mapping_shm.get_latest_payload(),
                                                          ),
                camera_configs=camera_configs)
        else:
            raise ValueError(f"Invalid retrieve_type: {retrieve_type}")

        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")

        # if retrieve_type == "next" and mf_payload.multi_frame_number % 10 == 0:
        #     print(f"\t\tGET MF FROM SHM -  multi-frame {mf_payload.multi_frame_number} from shared memory (took: {(tok - tik)/1e6:.3f}ms total, "
        #             f"\n\t\t\tfrom numpy: {(tik_from_numpy - tik)/1e6:.3f}ms)")
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
