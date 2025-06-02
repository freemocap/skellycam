import logging
import multiprocessing
import threading
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class CameraGroupOrchestrator:
    camera_frame_count: dict[CameraIdString, multiprocessing.Value]
    @classmethod
    def from_ipc(cls, ipc: CameraGroupIPC):
        return cls(camera_frame_count={camera_id: multiprocessing.Value("q", -1) for camera_id in ipc.camera_ids})

    @property
    def camera_ids(self):
        return list(self.camera_frame_count.keys())

    @property
    def all_cameras_ready(self):
        return all([flags.value for flags in self.camera_frame_count.values()])

    def should_grab_by_id(self, camera_id: CameraIdString) -> bool:
        if all([flag.value >= self.camera_frame_count[camera_id].value for flag in self.camera_frame_count.values()]):
            return True
        return False
