import logging
import multiprocessing
import time
from dataclasses import dataclass

from skellycam.core import CameraId
from skellycam.skellycam_app.skellycam_app_controller.ipc_flags import IPCFlags
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)

MAX_WAIT_TIME_S = 600.0


@dataclass
class CameraFrameLoopFlags:

    camera_id: CameraId

    camera_ready_flag: multiprocessing.Value
    frame_loop_initialization_flag: multiprocessing.Value
    should_grab_frame_flag: multiprocessing.Value
    should_retrieve_frame_flag: multiprocessing.Value
    should_copy_frame_into_shm_flag: multiprocessing.Value
    new_frame_in_shm: multiprocessing.Value
    close_self_flag: multiprocessing.Value

    ipc_flags: IPCFlags

    @classmethod
    def create(cls,
               camera_id: CameraId,
               ipc_flags: IPCFlags
               ):
        return cls(
            camera_id=camera_id,
            ipc_flags=ipc_flags,

            camera_ready_flag=multiprocessing.Value('b', False),
            frame_loop_initialization_flag=multiprocessing.Value('b', False),
            should_grab_frame_flag=multiprocessing.Value('b', False),
            should_retrieve_frame_flag=multiprocessing.Value('b', False),
            should_copy_frame_into_shm_flag=multiprocessing.Value('b', False),
            new_frame_in_shm=multiprocessing.Value('b', False),
            close_self_flag=multiprocessing.Value('b', False),

        )

    @property
    def should_continue(self):
        return self.ipc_flags.camera_group_should_continue and not self.close_self_flag.value

    def await_initialization_signal(self):
        self._wait_loop(self.frame_loop_initialization_flag, waiting_for="frame_read_initialization_flag")

        logger.loop(f"Camera {self.camera_id} process received `initial_trigger`")
        self.frame_loop_initialization_flag.value = False  # reset flag to signal that it has been received

    def await_should_grab_signal(self):
        self._wait_loop(self.should_grab_frame_flag, waiting_for="should_grab_frame_flag")

    def await_should_retrieve(self):
        self._wait_loop(self.should_retrieve_frame_flag, waiting_for="should_retrieve_frame_flag")

    def await_should_copy_frame_into_shm(self):
        self._wait_loop(self.should_copy_frame_into_shm_flag, waiting_for="should_copy_frame_into_shm_flag")

    def set_camera_not_ready(self):
        self.camera_ready_flag.value = False

    def set_camera_ready(self):
        self.camera_ready_flag.value = True

    def signal_frame_was_grabbed(self):
        self.should_grab_frame_flag.value = False

    def signal_frame_was_retrieved(self):
        self.should_retrieve_frame_flag.value = False

    def signal_new_frame_put_in_shm(self):
        self.new_frame_in_shm.value = True

    def _wait_loop(self, signal_flag: multiprocessing.Value, waiting_for:str,max_wait_time_s: float = MAX_WAIT_TIME_S):
        start_wait_ns = time.perf_counter_ns()
        been_warned = False
        while not signal_flag.value and self.should_continue:
            wait_1ms()
            been_warned = self._check_wait_time(max_wait_time_s=max_wait_time_s,
                                                waiting_for=waiting_for,
                                                start_wait_ns=start_wait_ns,
                                                been_warned=been_warned)

    def _check_wait_time(self, max_wait_time_s: float, waiting_for:str, start_wait_ns: float, been_warned: bool) -> bool:
        time_waited_s = (time.perf_counter_ns() - start_wait_ns) / 1e9
        if time_waited_s > max_wait_time_s * .01 and not been_warned:
            been_warned = True
            logger.warning(
                f"Camera {self.camera_id} process after waiting for {time_waited_s} seconds (reason: `{waiting_for}`:"
                f" self.grab_frame_trigger.value={self.should_grab_frame_flag.value}, "
                f"self.should_continue={self.should_continue}")

        if time_waited_s > max_wait_time_s:
            raise TimeoutError(
                f"Camera {self.camera_id} process timed out after waiting for {time_waited_s} seconds:"
                f" self.grab_frame_trigger.value={self.should_grab_frame_flag.value}, "
                f"self.should_continue={self.should_continue}")
        return been_warned

