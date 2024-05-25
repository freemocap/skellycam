import logging
import multiprocessing
import time

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig

logger = logging.getLogger(__name__)


class SingleCameraTriggers(BaseModel):
    camera_id: CameraId
    camera_ready_event: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    initial_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    grab_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    retrieve_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    copy_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_camera_id(cls, camera_id: CameraId):
        return cls(
            camera_id=camera_id,
        )

    def set_ready(self):
        self.camera_ready_event.set()

    def await_initial_trigger(self, wait_loop_time: float = 0.01):
        while not self.initial_trigger.is_set():
            time.sleep(wait_loop_time)
        logger.trace(f"Camera {self.camera_id} process received `initial_trigger`")
        self.initial_trigger.clear()

    def await_grab_trigger(self, wait_loop_time: float = 0.0001):
        while not self.grab_frame_trigger.is_set():
            time.sleep(0.0001)

    def set_frame_grabbed(self):
        self.grab_frame_trigger.clear()

    def await_retrieve_trigger(self, wait_loop_time: float = 0.0001):
        while not self.retrieve_frame_trigger.is_set():
            time.sleep(wait_loop_time)
        logger.trace(f"Camera {self.camera_id} process received `retrieve_frame_trigger`")

    def set_frame_retrieved(self):
        self.retrieve_frame_trigger.clear()