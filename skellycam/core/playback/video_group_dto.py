from dataclasses import dataclass
import multiprocessing

from skellycam.core.playback.video_config import VideoConfigs
from skellycam.skellycam_app.skellycam_app_controller.ipc_flags import IPCFlags


@dataclass
class VideoGroupDTO:
    video_configs: VideoConfigs

    ipc_queue: multiprocessing.Queue
    ipc_flags: IPCFlags
    
    group_uuid: str

    @property
    def video_ids(self):
        return list(self.video_configs.keys())