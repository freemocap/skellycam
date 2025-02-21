import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.skellycam_app.skellycam_app_controller.ipc_flags import IPCFlags


@dataclass
class CameraGroupDTO:
    camera_configs: CameraConfigs

    ipc_queue: multiprocessing.Queue
    logs_queue: multiprocessing.Queue
    ipc_flags: IPCFlags

    config_update_queue: multiprocessing.Queue
    group_uuid: str

    @property
    def camera_ids(self):
        return list(self.camera_configs.keys())

    @property
    def configs(self):  # TODO: this is to keep the camera group/video group API consistent. Could be handled with code at the interface level if that's preferred
        return self.camera_configs 

    @property
    def should_continue(self):
        return self.ipc_flags.camera_group_should_continue
