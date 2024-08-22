import logging
from typing import Dict, Optional, List

from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, GroupSharedMemoryNames

logger = logging.getLogger(__name__)


class CameraGroupSharedMemory(BaseModel):
    camera_configs: CameraConfigs
    camera_shms: Dict[CameraId, CameraSharedMemory]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def create(cls, camera_configs: CameraConfigs):
        camera_shms = {camera_id: CameraSharedMemory.create(camera_config=config)
                       for camera_id, config in camera_configs.items()}
        return cls(camera_configs=camera_configs,
                   camera_shms=camera_shms)

    @classmethod
    def recreate(cls,
                 camera_configs: CameraConfigs,
                 group_shm_names: GroupSharedMemoryNames):
        camera_shms = {camera_id: CameraSharedMemory.recreate(camera_config=config,
                                                              shared_memory_names=group_shm_names[
                                                                  camera_id])
                       for camera_id, config in camera_configs.items()}
        return cls(camera_configs=camera_configs,
                   camera_shms=camera_shms)

    @property
    def shared_memory_names(self) -> GroupSharedMemoryNames:
        return {camera_id: camera_shared_memory.shared_memory_names for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.camera_shms.keys())

    def get_multi_frame_payload(self, previous_payload: Optional[MultiFramePayload]) -> MultiFramePayload:
        if previous_payload is None:
            payload = MultiFramePayload.create_initial(camera_ids=self.camera_ids)
        else:
            payload = MultiFramePayload.from_previous(previous=previous_payload)

        for camera_id, camera_shared_memory in self.camera_shms.items():
            frame_dto = camera_shared_memory.retrieve_frame()
            payload.add_frame(frame_dto)
        if not payload.full:
            raise ValueError("Did not read full multi-frame payload!")
        return payload

    def get_camera_shared_memory(self, camera_id: CameraId) -> CameraSharedMemory:
        return self.camera_shms[camera_id]

    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
