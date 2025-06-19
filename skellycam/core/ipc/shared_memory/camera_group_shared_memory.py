import logging
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.multi_frame_payload_ring_buffer import MultiFrameSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)

CameraSharedMemoryDTOs = dict[CameraIdString, SharedMemoryRingBufferDTO]


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_shm_dtos: CameraSharedMemoryDTOs
    multi_frame_ring_shm_dto: SharedMemoryRingBufferDTO
    camera_configs: CameraConfigs


@dataclass
class CameraGroupSharedMemoryManager:
    camera_shms: dict[CameraIdString, FramePayloadSharedMemoryRingBuffer]
    multi_frame_ring_shm: MultiFrameSharedMemoryRingBuffer
    latest_multiframe_number: SharedMemoryNumber
    camera_configs: CameraConfigs
    read_only: bool
    _local_frames: dict[CameraIdString, FramePayload| None] = None
    _local_multiframe: MultiFramePayload | None = None

    original: bool = False

    @property
    def valid(self) -> bool:
        """
        Check if all cameras are ready and the shared memory is valid.
        """
        return all([
            all([camera_shared_memory.valid for camera_shared_memory in self.camera_shms.values()]),
            self.multi_frame_ring_shm.valid,
        ])

    @valid.setter
    def valid(self, value: bool):
        """
        Set the validity of the shared memory.
        This is used to invalidate the shared memory when it is no longer valid.
        """
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.valid = value

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               read_only: bool = False):
        return cls(camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.from_config(camera_config=config,
                                                                                          read_only=read_only)
                                for camera_id, config in camera_configs.items()},

                   multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.from_configs(
                       camera_configs=camera_configs,
                       read_only=read_only),
                   camera_configs=camera_configs,
                   original=True,
                   read_only=read_only,
                   latest_multiframe_number=SharedMemoryNumber.create(initial_value=-1, read_only=read_only),
                   )

    @classmethod
    def recreate(cls,
                 shm_dto: CameraGroupSharedMemoryDTO,
                 read_only: bool):

        return cls(
            camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                                read_only=read_only)
                         for camera_id, camera_shm_dto in shm_dto.camera_shm_dtos.items()},
            multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.recreate(
                dto=shm_dto.multi_frame_ring_shm_dto,
                read_only=read_only),
            camera_configs=shm_dto.camera_configs,
            latest_multiframe_number=SharedMemoryNumber.create(initial_value=-1, read_only=read_only),
            read_only=read_only)

    @property
    def camera_shm_dtos(self) -> CameraSharedMemoryDTOs:
        return {camera_id: camera_shared_memory.to_dto() for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_shms.keys())

    @property
    def new_multi_frame_available(self) -> bool:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return all([camera_shared_memory.new_frame_available
                    for camera_shared_memory in self.camera_shms.values()])

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_shm_dtos=self.camera_shm_dtos,
                                          multi_frame_ring_shm_dto=self.multi_frame_ring_shm.to_dto(),
                                          camera_configs=self.camera_configs
                                          )

    def build_next_multi_frame_payload(self) -> MultiFramePayload:
        """
        Retrieves the latest frame from each camera shm and copies it to the MultiFrameSharedMemoryRingBuffer.
        """
        if self.read_only:
            raise ValueError(
                "Cannot use `get_next_multi_frame_payload` in read-only mode - use `get_latest_multi_frame_payload` instead!")
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        if self._local_multiframe is None:
            self._local_multiframe = MultiFramePayload.create_empty(camera_configs=self.camera_configs)
        if self._local_frames is None:
            self._local_frames = {camera_id: None for camera_id in self.camera_ids}

        for camera_id, camera_shared_memory in self.camera_shms.items():
            if not camera_shared_memory.new_frame_available:
                raise ValueError(f"Camera {camera_id} does not have a new frame available!")

            self._local_frames[camera_id] = camera_shared_memory.retrieve_next_frame(self._local_frames[camera_id])

        if any([frame is None for frame in self._local_frames.values()]):
            raise ValueError(f"Not all cameras have new frames! Missing frames for cameras: {list(self._local_frames.keys())}")
        if not self._local_multiframe.full:
            if not all([frame.frame_number == -1 for frame in self._local_frames.values()]):
                raise ValueError(f"initialization mis-match! Some frames already have frame numbers: {[frame.frame_number for frame in self._local_frames.values()]}")
            [self._local_multiframe.add_frame(frame) for frame in self._local_frames.values()]
        else:
            if not all([frame.frame_number != self.latest_multiframe_number.value  for frame in self._local_frames.values()]):
                logger.warning(f"Frame number mismatch! Expected {self.latest_multiframe_number.value+ 1}, got {[self._local_frames[camera_id].frame_number for camera_id in self.camera_ids]}")
            self._local_multiframe.update_frames(self._local_frames)
        if not self._local_multiframe or not self._local_multiframe.full:
            raise ValueError("Did not read full multi-frame self._local_multiframe!")
        self.multi_frame_ring_shm.put_multiframe(mf_payload=self._local_multiframe,
                                                 overwrite=False)  # Don't overwrite to ensure all frames are saved
        self.latest_multiframe_number.value = self._local_multiframe.multi_frame_number
        logger.loop(f"Built multiframe #{self._local_multiframe.multi_frame_number} from cameras: {list(self._local_multiframe.camera_ids)}")

        return self._local_multiframe

    def build_all_new_multiframes(self) -> list[MultiFramePayload]:
        mfs: list[MultiFramePayload] = []
        while self.new_multi_frame_available:
            mf_payload = self.build_next_multi_frame_payload()
            mfs.append(mf_payload)
        return mfs

    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()
        self.multi_frame_ring_shm.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        if not self.original:
            raise RuntimeError(
                "Cannot unlink a non-original shared memory instance! Close child instances and unlink from the original instance instead.")
        self.valid = False
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()
        self.multi_frame_ring_shm.unlink()

    def unlink_and_close(self):
        self.unlink()
        self.close()
