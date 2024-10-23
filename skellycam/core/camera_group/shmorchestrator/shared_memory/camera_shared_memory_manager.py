import logging
import multiprocessing
from dataclasses import dataclass
from typing import Dict, Optional, List

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.camera_shared_memory import GroupSharedMemoryNames, \
    CameraSharedMemory
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_group_dto: CameraGroupDTO
    group_shm_names: GroupSharedMemoryNames
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value


@dataclass
class CameraGroupSharedMemory:
    camera_group_dto: CameraGroupDTO
    camera_shms: Dict[CameraId, CameraSharedMemory]
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value

    @classmethod
    def create(cls, camera_group_dto:CameraGroupDTO, read_only: bool = False):
        camera_shms = {camera_id: CameraSharedMemory.create(camera_config=config, read_only=read_only)
                       for camera_id, config in camera_group_dto.camera_configs.items()}

        return cls(camera_group_dto=camera_group_dto,
                   camera_shms=camera_shms,
                   shm_valid_flag=multiprocessing.Value('b', True),
                   latest_mf_number=multiprocessing.Value("l", -1))

    @classmethod
    def recreate(cls,
                 camera_group_dto: CameraGroupDTO,
                 shm_dto: CameraGroupSharedMemoryDTO,
                 read_only: bool):
        camera_shms = {camera_id: CameraSharedMemory.recreate(camera_config=config,
                                                              shared_memory_names=shm_dto.group_shm_names[
                                                                  camera_id],
                                                              read_only=read_only)
                       for camera_id, config in  camera_group_dto.camera_configs.items()}

        return cls(camera_group_dto=camera_group_dto,
                   camera_shms=camera_shms,
                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_mf_number=shm_dto.latest_mf_number)

    @property
    def shared_memory_names(self) -> GroupSharedMemoryNames:
        return {camera_id: camera_shared_memory.shared_memory_names for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.camera_group_dto.camera_ids.keys())

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_group_dto=self.camera_group_dto,
                                          group_shm_names=self.shared_memory_names,
                                          shm_valid_flag=self.shm_valid_flag,
                                          latest_mf_number=self.latest_mf_number)

    def get_multi_frame_payload(self,
                                previous_payload: Optional[MultiFramePayload],
                                camera_configs: CameraConfigs
                                ) -> MultiFramePayload:

        if previous_payload is None:
            payload: MultiFramePayload = MultiFramePayload.create_initial(camera_configs=camera_configs)
        else:
            payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                         camera_configs=camera_configs)

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        for camera_id, camera_shared_memory in self.camera_shms.items():
            frame = camera_shared_memory.retrieve_frame()
            payload.add_frame(frame)
        if not payload.full:
            raise ValueError("Did not read full multi-frame payload!")
        self.latest_mf_number.value = payload.multi_frame_number
        return payload

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
