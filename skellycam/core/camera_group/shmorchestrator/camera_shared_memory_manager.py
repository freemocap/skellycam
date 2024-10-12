import logging
import multiprocessing
from dataclasses import dataclass
from typing import Dict, Optional, List

from pydantic import BaseModel, ConfigDict, Field

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory import CameraSharedMemory, GroupSharedMemoryNames
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_configs: CameraConfigs
    group_shm_names: GroupSharedMemoryNames
    shm_valid_flag: multiprocessing.Value


@dataclass
class CameraGroupSharedMemory:
    camera_configs: CameraConfigs
    camera_shms: Dict[CameraId, CameraSharedMemory]
    shm_valid_flag: multiprocessing.Value = multiprocessing.Value("b", True)

    @classmethod
    def create(cls, camera_configs: CameraConfigs, read_only: bool = False):
        camera_shms = {camera_id: CameraSharedMemory.create(camera_config=config, read_only=read_only)
                       for camera_id, config in camera_configs.items()}

        return cls(camera_configs=camera_configs,
                   camera_shms=camera_shms)

    @classmethod
    def recreate(cls,
                 dto: CameraGroupSharedMemoryDTO,
                 read_only: bool):
        camera_shms = {camera_id: CameraSharedMemory.recreate(camera_config=config,
                                                              shared_memory_names=dto.group_shm_names[
                                                                  camera_id],
                                                              read_only=read_only)
                       for camera_id, config in dto.camera_configs.items()}

        return cls(camera_configs=dto.camera_configs,
                   camera_shms=camera_shms,
                   shm_valid_flag=dto.shm_valid_flag)

    @property
    def shared_memory_names(self) -> GroupSharedMemoryNames:
        return {camera_id: camera_shared_memory.shared_memory_names for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.camera_shms.keys())

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_configs=self.camera_configs,
                                          group_shm_names=self.shared_memory_names,
                                          shm_valid_flag=self.shm_valid_flag)

    def get_multi_frame_payload(self,
                                previous_payload: Optional[MultiFramePayload]
                                ) -> MultiFramePayload:

        if previous_payload is None:
            payload = MultiFramePayload.create_initial(camera_configs=self.camera_configs)
        else:
            payload = MultiFramePayload.from_previous(previous=previous_payload, camera_configs=self.camera_configs)

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        for camera_id, camera_shared_memory in self.camera_shms.items():
            frame = camera_shared_memory.retrieve_frame()
            payload.add_frame(frame)
        if not payload.full:
            raise ValueError("Did not read full multi-frame payload!")

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
