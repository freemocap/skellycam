from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.skellycam_app.skellycam_app_ipc.ipc_manager import InterProcessCommunicationManager


@dataclass
class CameraGroupDTO:
    camera_configs: CameraConfigs
    ipc: InterProcessCommunicationManager
    group_uuid: str

    @property
    def should_continue(self):
        return self.ipc.camera_group_should_continue