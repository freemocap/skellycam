import logging
import multiprocessing
import time
from multiprocessing import synchronize

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig

logger = logging.getLogger(__name__)


class SingleCameraTriggers(BaseModel):
    camera_id: CameraId
    initial_trigger: synchronize.Event
    grab_frame_trigger: synchronize.Event
    frame_grabbed_trigger: synchronize.Event
    retrieve_frame_trigger: synchronize.Event
    camera_ready_event: synchronize.Event

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_camera_config(cls, camera_config: CameraConfig):
        return cls(
            camera_id=CameraId(camera_config.camera_id),
            camera_ready_event=multiprocessing.Event(),
            initial_trigger=multiprocessing.Event(),
            grab_frame_trigger=multiprocessing.Event(),
            frame_grabbed_trigger=multiprocessing.Event(),
            retrieve_frame_trigger=multiprocessing.Event(),
        )

    def set_ready(self):
        self.camera_ready_event.set()

    def set_frame_grabbed(self):
        self.frame_grabbed_trigger.set()

    def await_initial_trigger(self, wait_loop_time: float = 0.01):
        while not self.initial_trigger.is_set():
            time.sleep(wait_loop_time)
        logger.trace(f"Camera {self.camera_id} process received `initial_trigger`")
        self.initial_trigger.clear()

    def await_retrieve_trigger(self, wait_loop_time: float = 0.0001):
        while not self.retrieve_frame_trigger.is_set():
            time.sleep(wait_loop_time)
        logger.trace(f"Camera {self.camera_id} process received `retrieve_frame_trigger`")

    def await_grab_trigger(self, wait_loop_time: float = 0.0001):
        while not self.grab_frame_trigger.is_set():
            time.sleep(0.0001)
    def clear_frame_triggers(self):
        self.grab_frame_trigger.clear()
        self.frame_grabbed_trigger.clear()
        self.retrieve_frame_trigger.clear()