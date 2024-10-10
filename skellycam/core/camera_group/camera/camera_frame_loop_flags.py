import logging
import multiprocessing
import time

from pydantic import BaseModel, Field, ConfigDict

from skellycam.app.app_controller.ipc_flags import IPCFlags
from skellycam.core import CameraId
from skellycam.utilities.wait_functions import wait_100us, wait_10ms

logger = logging.getLogger(__name__)

MAX_WAIT_TIME_S = 60.0


class CameraFrameLoopFlags(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    camera_id: CameraId
    camera_ready_flag: multiprocessing.Value = Field(default_factory=lambda: multiprocessing.Value("b", False))
    frame_loop_initialization_flag: multiprocessing.Value = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    should_grab_frame_flag: multiprocessing.Value = Field(default_factory=lambda: multiprocessing.Value("b", False))
    should_retrieve_frame_flag: multiprocessing.Value = Field(default_factory=lambda: multiprocessing.Value("b", False))
    new_frame_available_flag: multiprocessing.Value = Field(
        default_factory=lambda: multiprocessing.Value("b", False))

    close_self_flag: multiprocessing.Value = Field(default_factory=lambda: multiprocessing.Value("b", False))

    ipc_flags: IPCFlags

    @classmethod
    def create(cls,
               camera_id: CameraId,
               ipc_flags: IPCFlags
               ):
        return cls(
            camera_id=camera_id,
            ipc_flags=ipc_flags,
        )

    @property
    def should_continue(self):
        return not self.ipc_flags.global_kill_flag.value and not self.ipc_flags.kill_camera_group_flag.is_set() and not self.close_self_flag.is_set()

    def await_frame_loop_initialization(self, max_wait_time_s: float = MAX_WAIT_TIME_S):
        start_wait_ns = time.perf_counter_ns()
        been_warned = False
        while not self.frame_loop_initialization_flag.value and self.should_continue:
            wait_10ms()
            self._check_wait_time(max_wait_time_s, start_wait_ns, been_warned)

        logger.trace(f"Camera {self.camera_id} process received `initial_trigger`")
        self.frame_loop_initialization_flag.value = False

    def await_should_retrieve(self, max_wait_time_s: float = MAX_WAIT_TIME_S):
        start_wait_ns = time.perf_counter_ns()
        been_warned = False
        while not self.should_retrieve_frame_flag.value and self.should_continue:
            wait_100us()
            self._check_wait_time(max_wait_time_s, start_wait_ns, been_warned)
        logger.loop(f"Camera {self.camera_id} process received `retrieve_frame_trigger`")

    def await_should_grab(self, max_wait_time_s: float = MAX_WAIT_TIME_S):
        start_wait_ns = time.perf_counter_ns()
        been_warned = False
        while not self.should_grab_frame_flag.value and self.should_continue:
            wait_100us()
            self._check_wait_time(max_wait_time_s, start_wait_ns, been_warned)

    def set_camera_not_ready(self):
        self.camera_ready_flag.value = False

    def set_camera_ready(self):
        self.camera_ready_flag.value = True

    def set_frame_grabbed(self):
        self.should_grab_frame_flag.value = False

    def set_frame_retrieved(self):
        self.should_retrieve_frame_flag.value = False

    def set_new_frame_available(self):
        self.new_frame_available_flag.value = True

    def _check_wait_time(self, max_wait_time_s: float, start_wait_ns: float, been_warned: bool):
        time_waited_s = (time.perf_counter_ns() - start_wait_ns)
        if time_waited_s > (max_wait_time_s * 1e9) * .5 and not been_warned:
            logger.warning(
                f"Camera {self.camera_id} process hit half-way point waiting for `grab_frame_trigger` for {time_waited_s} seconds:"
                f" self.grab_frame_trigger.is_set()={self.should_grab_frame_flag.is_set()}, "
                f"self.should_continue={self.should_continue}")

        if time_waited_s > max_wait_time_s * 1e9:
            raise TimeoutError(
                f"Camera {self.camera_id} process timed out waiting for `grab_frame_trigger` for {time_waited_s} seconds:"
                f" self.grab_frame_trigger.is_set()={self.should_grab_frame_flag.is_set()}, "
                f"self.should_continue={self.should_continue}")
