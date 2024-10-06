import logging
import multiprocessing
import time

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, SkipValidation
from typing_extensions import Annotated

from skellycam.core import CameraId
from skellycam.utilities.wait_functions import wait_100us, wait_10ms

logger = logging.getLogger(__name__)


class CameraTriggers(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    camera_id: CameraId
    camera_ready_event: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    initial_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    grab_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    retrieve_frame_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)
    new_frame_available_trigger: multiprocessing.Event = Field(default_factory=multiprocessing.Event)

    close_self_event: multiprocessing.Event = Field(default_factory=multiprocessing.Event)

    _kill_camera_group_flag: Annotated[multiprocessing.Value, SkipValidation] = PrivateAttr()
    _global_kill_event: Annotated[multiprocessing.Event, SkipValidation] = PrivateAttr()

    @classmethod
    def from_camera_id(cls,
                       camera_id: CameraId,
                       kill_camera_group_flag: multiprocessing.Value,
                       global_kill_event: multiprocessing.Event
                       ):
        return cls(
            camera_id=camera_id,
            _kill_camera_group_flag=kill_camera_group_flag,
            _global_kill_event=global_kill_event
        )

    def __init__(self, **data):
        super().__init__(**data)
        self._kill_camera_group_flag = data.get('_kill_camera_group_flag')
        self._global_kill_event = data.get('_global_kill_event')

    @property
    def should_continue(self):
        return not self._kill_camera_group_flag.value and not self._global_kill_event.is_set() and not self.close_self_event.is_set()

    def await_initial_trigger(self, max_wait_time_s: float = 60.0):
        start_wait_ns = time.perf_counter_ns()
        while not self.initial_trigger.is_set() and self.should_continue:
            wait_10ms()
            time_waited_s = (time.perf_counter_ns() - start_wait_ns) / 1e9
            if  time_waited_s> max_wait_time_s:
                raise TimeoutError(
                    f"Camera {self.camera_id} process timed out waiting for `initial_trigger` for {time_waited_s} seconds:"
                    f" self.initial_trigger.is_set()={self.initial_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}")

        logger.trace(f"Camera {self.camera_id} process received `initial_trigger`")
        self.initial_trigger.clear()

    def await_retrieve_trigger(self, max_wait_time_s: float = 300.0):
        start_wait_ns = time.perf_counter_ns()
        while not self.retrieve_frame_trigger.is_set() and self.should_continue:
            wait_100us()
            time_waited_s = (time.perf_counter_ns() - start_wait_ns)
            if time_waited_s  > max_wait_time_s * 1e9:
                raise TimeoutError(
                    f"Camera {self.camera_id} process timed out waiting for `retrieve_frame_trigger` for {time_waited_s} seconds:"
                    f"self.retrieve_frame_trigger.is_set()={self.retrieve_frame_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}")
        logger.loop(f"Camera {self.camera_id} process received `retrieve_frame_trigger`")

    def await_grab_trigger(self, max_wait_time_s: float = 300.0):
        start_wait_ns = time.perf_counter_ns()
        been_warned = False
        while not self.grab_frame_trigger.is_set() and self.should_continue:
            wait_100us()
            time_waited_s = (time.perf_counter_ns() - start_wait_ns)
            if time_waited_s  > (max_wait_time_s * 1e9) * .5 and not been_warned:
                been_warned = True
                logger.warning(
                    f"Camera {self.camera_id} process hit half-way point waiting for `grab_frame_trigger` for {time_waited_s} seconds:"
                    f" self.grab_frame_trigger.is_set()={self.grab_frame_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}")

                time_waited_s = (time.perf_counter_ns() - start_wait_ns)
            if time_waited_s  > max_wait_time_s * 1e9:
                raise TimeoutError(
                    f"Camera {self.camera_id} process timed out waiting for `grab_frame_trigger` for {time_waited_s} seconds:"
                    f" self.grab_frame_trigger.is_set()={self.grab_frame_trigger.is_set()}, "
                    f"self.should_continue={self.should_continue}")

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
