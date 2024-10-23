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

    config_update_queue = multiprocessing.Queue()  # Update camera configs
    group_uuid: str
    _lock = multiprocessing.Lock()

    @property
    def camera_ids(self):
        return list(self.camera_configs.keys())

    def update_camera_configs(self, camera_configs: CameraConfigs):
        with self._lock:
            self.camera_configs = camera_configs

    def __post_init__(self):
        if not self.camera_configs:
            raise ValueError(f"CameraConfigs not set: self.camera_configs={self.camera_configs}")
        if not self.shmorc_dto:
            raise ValueError(f"CameraGroupSharedMemoryOrchestratorDTO not set: self.shmorc_dto={self.shmorc_dto}")
        if not self.ipc_queue:
            raise ValueError(f"IPC Queue not set: self.ipc_queue={self.ipc_queue}")
        if not self.ipc_flags:
            raise ValueError(f"IPC Flags not set: self.ipc_flags={self.ipc_flags}")
        if not self.config_update_queue:
            raise ValueError(f"Config Update Queue not set: self.config_update_queue={self.config_update_queue}")
        if not self._lock:
            raise ValueError(f"Lock not set: self._lock={self._lock}")
        if not self.camera_ids:
            raise ValueError(f"Camera IDs not set: self.camera_ids={self.camera_ids}")