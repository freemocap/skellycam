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
    ipc: CameraGroupIPC
    camera_ready_flags: dict[CameraIdString, multiprocessing.Value]
    grab_frame_counter: multiprocessing.Value
    ludacris_speed: bool # skip the 1ms wait for faster response, likely to no benefit and with a high CPU cost (default: False)
    @classmethod
    def from_ipc(cls, ipc: CameraGroupIPC, ludacris_speed:bool=False):
        return cls(ipc=ipc,
                   camera_ready_flags={ camera_id: multiprocessing.Value("b", False) for camera_id in ipc.camera_ids },
                   grab_frame_counter = multiprocessing.Value("q", -1),
                   ludacris_speed=ludacris_speed)

    @property
    def camera_ids(self):
        return list(self.camera_ready_flags.keys())


    def run_frame_loop(self):
        # Await all cameras are ready
        self.await_cameras_ready()

        wait_1ms() if not self.ludacris_speed else None
        #  Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()`
        self.trigger_frame_grab()
        wait_1ms() if not self.ludacris_speed else None


    @property
    def all_cameras_ready(self):
        return all([flags.value for flags in self.camera_ready_flags.values()])

    def await_cameras_ready(self):
        while not self.all_cameras_ready and self.ipc.should_continue:
            wait_1ms() if not self.ludacris_speed else None

    def trigger_frame_grab(self):
        for camera_id, flags in self.camera_ready_flags.items():
            flags.camera_ready_flag.value = False #pre-emptively set camera ready flag to False
        self.grab_frame_counter.value += 1 #trigger the cameras to grab a frame by incrementing the counter


