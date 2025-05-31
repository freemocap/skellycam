import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer, \
    FramePayloadSharedMemoryRingBufferDTO
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)

CameraSharedMemoryDTOs = dict[CameraIdString, FramePayloadSharedMemoryRingBufferDTO]


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_configs: CameraConfigs
    camera_shm_dtos: CameraSharedMemoryDTOs
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value


@dataclass
class CameraGroupSharedMemory:
    ipc: CameraGroupIPC
    camera_shms: dict[CameraIdString, FramePayloadSharedMemoryRingBuffer]
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value
    read_only: bool

    @classmethod
    def from_ipc(cls,
                 camera_group_ipc: CameraGroupIPC,
                 read_only: bool = False):
        camera_shms = {camera_id: FramePayloadSharedMemoryRingBuffer.create(camera_config=config,
                                                                            read_only=read_only)
                       for camera_id, config in camera_group_ipc.camera_configs.items()}

        return cls(ipc=camera_group_ipc,
                   camera_shms=camera_shms,
                   shm_valid_flag=multiprocessing.Value('b', True),
                   latest_mf_number=multiprocessing.Value("l", -1),
                   read_only=read_only)

    @classmethod
    def recreate_from_dto(cls,
                          ipc: CameraGroupIPC,
                          shm_dto: CameraGroupSharedMemoryDTO,
                          read_only: bool):
        camera_shms = {camera_id: FramePayloadSharedMemoryRingBuffer.recreate(dto=shm_dto.camera_shm_dtos[
                                                                                  camera_id],
                                                                              read_only=read_only)
                       for camera_id, config in shm_dto.camera_configs.items()}

        return cls(ipc=ipc,
                   camera_shms=camera_shms,
                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_mf_number=shm_dto.latest_mf_number,
                   read_only=read_only)

    @property
    def camera_shm_dtos(self) -> CameraSharedMemoryDTOs:
        return {camera_id: camera_shared_memory.to_dto() for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_shms.keys())

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_configs=self.camera_configs,
                                          camera_shm_dtos=self.camera_shm_dtos,
                                          shm_valid_flag=self.shm_valid_flag,
                                          latest_mf_number=self.latest_mf_number)

    def get_multi_frame_payload(self,
                                previous_payload: MultiFramePayload | None,
                                camera_configs: CameraConfigs,
                                ) -> MultiFramePayload:

        if previous_payload is None:
            mf_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_configs=camera_configs)
        else:
            mf_payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                            camera_configs=camera_configs)

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        for camera_id, camera_shared_memory in self.camera_shms.items():
            if not camera_shared_memory.new_frame_available:
                raise ValueError(f"Camera {camera_id} does not have a new frame available!")

            frame = camera_shared_memory.retrieve_frame()
            if frame.frame_number != self.latest_mf_number.value + 1:
                raise ValueError(
                    f"Frame number mismatch! Expected {self.latest_mf_number.value + 1}, got {frame.frame_number}")
            mf_payload.add_frame(frame)
        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        if not self.read_only:
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
