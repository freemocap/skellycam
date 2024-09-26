import logging
import multiprocessing
import time

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, SkipValidation
from typing_extensions import Annotated

from skellycam.core import CameraId
from skellycam.utilities.wait_functions import wait_10us, wait_10ms

logger = logging.getLogger(__name__)


class CameraTriggers(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    camera_id: CameraId
    camera_ready_event: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    initial_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    grab_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    retrieve_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    new_frame_available_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    _kill_camera_group_flag: Annotated[multiprocessing.Value, SkipValidation] = PrivateAttr()

    @classmethod
    def from_camera_id(cls,
                       camera_id: CameraId,
                       kill_camera_group_flag: multiprocessing.Value
                       ):
        return cls(
            camera_id=camera_id,
            _kill_camera_group_flag=kill_camera_group_flag
        )

    def __init__(self, **data):
        super().__init__(**data)
        self._kill_camera_group_flag = data.get('_kill_camera_group_flag')


    @property
    def should_continue(self):
        return not self._kill_camera_group_flag.value

    def await_initial_trigger(self, close_self_flag: multiprocessing.Value, max_wait_time_s: float = 60.0):
        start_wait_ns = time.perf_counter_ns()
        while not self.initial_trigger.is_set() and self.should_continue and not close_self_flag.value:
            wait_10ms()
            if (time.perf_counter_ns() - start_wait_ns) > max_wait_time_s * 1e9:
                raise TimeoutError(
                    f"Camera {self.camera_id} process timed out waiting for `initial_trigger` for {max_wait_time_s} seconds:"
                    f" self.initial_trigger.is_set()={self.initial_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}, "
                    f"close_self_flag.value={close_self_flag.value}")

        logger.trace(f"Camera {self.camera_id} process received `initial_trigger`")
        self.initial_trigger.clear()

    def await_retrieve_trigger(self, close_self_flag: multiprocessing.Value, max_wait_time_s: float = 5000.0):
        start_wait_ns = time.perf_counter_ns()
        while not self.retrieve_frame_trigger.is_set() and self.should_continue and not close_self_flag.value:
            wait_10us()
            if (time.perf_counter_ns() - start_wait_ns) > max_wait_time_s * 1e9:
                raise TimeoutError(
                    f"Camera {self.camera_id} process timed out waiting for `retrieve_frame_trigger` for {max_wait_time_s} seconds:"
                    f"self.retrieve_frame_trigger.is_set()={self.retrieve_frame_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}, "
                    f"close_self_flag.value={close_self_flag.value}")
        logger.loop(f"Camera {self.camera_id} process received `retrieve_frame_trigger`")

    def await_grab_trigger(self, close_self_flag: multiprocessing.Value, max_wait_time_s: float = 5000.0):
        start_wait_ns = time.perf_counter_ns()
        been_warned = False
        while not self.grab_frame_trigger.is_set() and self.should_continue and not close_self_flag.value:
            wait_10us()
            if (time.perf_counter_ns() - start_wait_ns) > (max_wait_time_s * 1e9)*.5 and not been_warned:
                been_warned = True
                logger.warning(f"Camera {self.camera_id} process hit half-way point waiting for `grab_frame_trigger` for {max_wait_time_s} seconds:"
                               f" self.grab_frame_trigger.is_set()={self.grab_frame_trigger.is_set()}, "
                               f"self.should_continue={self.should_continue}, "
                               f"close_self_flag.value={close_self_flag.value}")

            if (time.perf_counter_ns() - start_wait_ns) > max_wait_time_s * 1e9:
                raise TimeoutError(
                    f"Camera {self.camera_id} process timed out waiting for `grab_frame_trigger` for {max_wait_time_s} seconds:"
                    f" self.grab_frame_trigger.is_set()={self.grab_frame_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}, "
                    f"close_self_flag.value={close_self_flag.value}")

    def set_not_ready(self):
        self.camera_ready_event.set()
    def set_ready(self):
        self.camera_ready_event.set()

    def set_frame_grabbed(self):
        self.grab_frame_trigger.clear()

    def set_frame_retrieved(self):
        self.retrieve_frame_trigger.clear()

    def set_new_frame_available(self):
        self.new_frame_available_trigger.set()


