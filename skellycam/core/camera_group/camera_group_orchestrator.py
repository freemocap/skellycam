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
    camera_frame_counts: dict[CameraIdString, multiprocessing.Value]
    camera_ready_flags: dict[CameraIdString, multiprocessing.Value] = None
    @classmethod
    def from_ipc(cls, ipc: CameraGroupIPC):
        return cls(camera_frame_counts={camera_id: multiprocessing.Value("q", -1) for camera_id in ipc.camera_ids},
                   camera_ready_flags={camera_id: multiprocessing.Value('b',0) for camera_id in ipc.camera_ids})

    @property
    def camera_ids(self):
        return list(self.camera_frame_counts.keys())

    @property
    def all_cameras_ready(self):
        return all([flags.value for flags in self.camera_ready_flags.values()])

    def should_grab_by_id(self, camera_id: CameraIdString) -> bool:
        if self.all_cameras_ready and all ([flag.value >= self.camera_frame_counts[camera_id].value for flag in self.camera_frame_counts.values()]):
            return True
        return False
