import logging
import multiprocessing
from typing import Dict, Optional, List

from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory import CameraSharedMemory, GroupSharedMemoryNames
from skellycam.core.camera_group.shmorchestrator.shared_memory_number import SharedMemoryNumber

logger = logging.getLogger(__name__)


class CameraGroupSharedMemoryDTO(BaseModel):
    camera_configs: CameraConfigs
    group_shm_names: GroupSharedMemoryNames
    mf_counter_shm_name: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CameraGroupSharedMemory(BaseModel):
    camera_configs: CameraConfigs
    camera_shms: Dict[CameraId, CameraSharedMemory]
    multi_frame_number_shm: SharedMemoryNumber
    shm_valid_flag: multiprocessing.Value

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls, camera_configs: CameraConfigs, read_only: bool = False):
        camera_shms = {camera_id: CameraSharedMemory.create(camera_config=config, read_only=read_only)
                       for camera_id, config in camera_configs.items()}

        return cls(camera_configs=camera_configs,
                   camera_shms=camera_shms,
                   multi_frame_number_shm=SharedMemoryNumber.create(),
                   shm_valid_flag=multiprocessing.Value("b", True))

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
                   multi_frame_number_shm=SharedMemoryNumber.recreate(dto.mf_counter_shm_name),
                   shm_valid_flag=dto.shm_valid_flag)

    @property
    def shared_memory_names(self) -> GroupSharedMemoryNames:
        return {camera_id: camera_shared_memory.shared_memory_names for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.camera_shms.keys())

    @property
    def multi_frame_number(self) -> int:
        return self.multi_frame_number_shm.get()

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_configs=self.camera_configs,
                                          group_shm_names=self.shared_memory_names,
                                          mf_counter_shm_name=self.multi_frame_number_shm.name)

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
        if not self.read_only:
            # Only increment the multi-frame number if this is not a read-only instance of the shared memory
            self.multi_frame_number_shm.set(payload.multi_frame_number)
        return payload


    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it        
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()
        self.multi_frame_number_shm.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        self.shm_valid_flag.value = False
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()
        self.multi_frame_number_shm.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
