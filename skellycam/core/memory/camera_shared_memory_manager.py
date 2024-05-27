import logging
from typing import Dict

from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames

logger = logging.getLogger(__name__)


class CameraSharedMemoryManager(BaseModel):
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
    def recreate(cls, camera_configs: CameraConfigs, existing_shared_memory_names: Dict[CameraId, SharedMemoryNames]):
        camera_shms = {camera_id: CameraSharedMemory.recreate(camera_config=config,
                                                              shared_memory_names=existing_shared_memory_names[
                                                                  camera_id])
                       for camera_id, config in camera_configs.items()}
        return cls(camera_configs=camera_configs,
                   camera_shms=camera_shms)

    @property
    def shared_memory_names(self) -> Dict[CameraId, SharedMemoryNames]:
        return {camera_id: camera_shared_memory.shared_memory_names for camera_id, camera_shared_memory in
                self._camera_shms.items()}

    def get_multi_frame_payload(self) -> MultiFramePayload:
        payload = MultiFramePayload(camera_ids=self.camera_configs.keys())
        for camera_id, camera_shared_memory in self._camera_shms.items():
            payload.add_frame(camera_shared_memory.retrieve_frame_mv())
        if not payload.full:
            raise ValueError("Did not read full multi-frame payload!")
        return payload

    def get_camera_shared_memory(self, camera_id: CameraId) -> CameraSharedMemory:
        return self._camera_shms[camera_id]

    def close(self):
        for camera_shared_memory in self._camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        for camera_shared_memory in self._camera_shms.values():
            camera_shared_memory.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
