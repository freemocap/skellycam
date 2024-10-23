import multiprocessing
from dataclasses import dataclass
from uuid import uuid4

from skellycam.app.app_controller.ipc_flags import IPCFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO


@dataclass
class CameraGroupDTO:
    camera_configs: CameraConfigs
    shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO
    ipc_queue: multiprocessing.Queue
    ipc_flags: IPCFlags

    config_update_queue: multiprocessing.Queue
    group_uuid: str
    _lock = multiprocessing.Lock()

    @property
    def camera_ids(self):
        return list(self.camera_configs.keys())

    def update_camera_configs(self, camera_configs: CameraConfigs):
        with self._lock:
            self.camera_configs = camera_configs

