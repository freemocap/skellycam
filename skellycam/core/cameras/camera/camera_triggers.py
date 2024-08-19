import logging
import multiprocessing

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, SkipValidation
from typing_extensions import Annotated

from skellycam.core import CameraId
from skellycam.utilities.wait_functions import wait_1us, wait_10ms

logger = logging.getLogger(__name__)


class CameraTriggers(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    camera_id: CameraId
    camera_ready_event: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    initial_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    grab_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    retrieve_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    new_frame_available_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    _exit_event: Annotated[multiprocessing.Event, SkipValidation] = PrivateAttr()

    @classmethod
    def from_camera_id(cls,
                       camera_id: CameraId,
                       exit_event: multiprocessing.Event
                       ):
        return cls(
            camera_id=camera_id,
            _exit_event=exit_event
        )

    def __init__(self, **data):
        super().__init__(**data)
        self._exit_event = data.get('_exit_event')

    @property
    def new_frame_available(self):
        return self.new_frame_available_trigger.is_set()

    @property
    def should_continue(self):
        return not self._exit_event.is_set()

    def set_ready(self):
        self.camera_ready_event.set()

    def await_initial_trigger(self):
        while not self.initial_trigger.is_set() and self.should_continue:
            wait_10ms()
        logger.trace(f"Camera {self.camera_id} process received `initial_trigger`")
        self.initial_trigger.clear()

    def await_grab_trigger(self, wait_loop_time: float = 0.0001):
        while not self.grab_frame_trigger.is_set() and self.should_continue:
            wait_1us()

    def set_frame_grabbed(self):
        self.grab_frame_trigger.clear()

    def await_retrieve_trigger(self):
        while not self.retrieve_frame_trigger.is_set() and self.should_continue:
            wait_1us()
        logger.trace(f"Camera {self.camera_id} process received `retrieve_frame_trigger`")

    def set_frame_retrieved(self):
        self.retrieve_frame_trigger.clear()
        self.new_frame_available_trigger.set()

    def set_frame_copied(self):
        self.new_frame_available_trigger.clear()

    def clear_all(self):
        self.camera_ready_event.clear()
        self.initial_trigger.clear()
        self.grab_frame_trigger.clear()
        self.retrieve_frame_trigger.clear()
        self.new_frame_available_trigger.clear()


