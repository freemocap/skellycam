import logging
import multiprocessing
from dataclasses import dataclass
from typing import Dict

from skellycam.app.app_controller.ipc_flags import IPCFlags
from skellycam.core import CameraId
from skellycam.core.camera_group.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.utilities.wait_functions import wait_100us, wait_1ms, wait_10ms, wait_100ms

logger = logging.getLogger(__name__)


@dataclass
class CameraGroupOrchestrator:
    frame_loop_flags: Dict[CameraId, CameraFrameLoopFlags]
    ipc_flags: IPCFlags

    new_multi_frame_available_flag: multiprocessing.Value = multiprocessing.Value("b", False)

    pause_when_able: multiprocessing.Value = multiprocessing.Value("b", False)
    frame_loop_paused: multiprocessing.Value = multiprocessing.Value("b", False)

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               ipc_flags: IPCFlags):
        return cls(
            frame_loop_flags={
                camera_id: CameraFrameLoopFlags.create(camera_id=camera_id,
                                                       ipc_flags=ipc_flags)
                for camera_id, camera_config in camera_configs.items()
            },
            ipc_flags=ipc_flags
        )

    @property
    def camera_ids(self):
        return list(self.frame_loop_flags.keys())

    @property
    def should_continue(self):
        return not self.ipc_flags.kill_camera_group_flag.value and not self.ipc_flags.global_kill_flag.value

    @property
    def cameras_ready(self):
        return all([triggers.camera_ready_flag.value for triggers in self.frame_loop_flags.values()])

    @property
    def new_multi_frame_available(self):
        return all([triggers.new_frame_available_flag.value for triggers in self.frame_loop_flags.values()])

    @property
    def frames_grabbed(self):
        return not any([triggers.should_grab_frame_flag.value for triggers in self.frame_loop_flags.values()])

    @property
    def frames_retrieved(self):
        return not any([triggers.should_retrieve_frame_flag.value for triggers in self.frame_loop_flags.values()])

    def pause_loop(self):
        self.pause_when_able.value = True

    def unpause_loop(self):
        self.pause_when_able.value = False

    ##############################################################################################################
    def trigger_multi_frame_read(self):

        if self.pause_when_able.value:
            logger.trace("Pause requested, pausing frame loop...")
            self.frame_loop_paused.value = True
            while self.pause_when_able.value and self.should_continue:
                wait_100ms()
            if self.should_continue:
                logger.trace("Loop unpaused, awaiting cameras ready...")
                self.frame_loop_paused.value = False
                self.await_cameras_ready()

        # 0 - Make sure all cameras are ready
        logger.loop(f"FRAME LOOP BEGIN")
        logger.loop(f"**Frame Loop** - Step #0 (start)  - Make sure all cameras are ready")
        self._ensure_cameras_ready()
        logger.loop(f"**Frame Loop** - Step #0 (finish) - All cameras are ready!")

        # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
        logger.loop(f"**Frame Loop** - Step #1 (start) - Fire grab triggers")
        self._fire_grab_trigger()
        logger.loop(f"**Frame Loop** - Step #1 (finish) - GRAB triggers fired!")

        # 2 - wait for all cameras to grab a frame
        logger.loop(f"**Frame Loop** - Step #2 (start) - Wait for all cameras to GRAB a frame")
        self._await_frames_grabbed()
        logger.loop(f"**Frame Loop** - Step #2 (finish) - All cameras have GRABbed a frame!")

        # 3- Trigger each camera to retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
        logger.loop(f"**Frame Loop** - Step #3 (start)- Fire retrieve triggers")
        self._fire_retrieve_trigger()
        logger.loop(f"**Frame Loop** - Step #3 (finish) - RETRIEVE triggers fired!")

        # 4 - wait for all cameras to retrieve the frame and put it in shared memory
        logger.loop(f"**Frame Loop** - Step #4 (start) - Wait for new multi-frame to be available")
        self.await_new_multi_frame_available()
        logger.loop(
            f"**Frame Loop** - Step #4 (finish) - New multi-frame available in shared memory!")

        # 6 - wait for the frame to be copied from the `write` buffer to the `read` buffer
        logger.loop(
            f"**Frame Loop** - Step #7 (start) - Wait for multi-frame to be copied from shared memory")
        self._await_mf_copied_from_shm()
        logger.loop(
            f"**Frame Loop** - Step #7 (finish) - Multi-frame copied from shared memory!")

        # 7 - Make sure all the triggers are as they should be
        logger.loop(
            f"**Frame Loop** - Step# 8 (start) - Verify that everything is hunky-dory after reading the frames")
        self._verify_hunky_dory_after_read()
        logger.loop(
            f"**Frame Loop** - Step #8 (end) - Everything is hunky-dory after reading the frames!")
        logger.loop(f"FRAME LOOP Complete!")

    ##############################################################################################################

    def signal_frame_loop_started(self):
        self._ensure_cameras_ready()

        logger.debug(f"Firing initial triggers for all cameras...")
        for triggers in self.frame_loop_flags.values():
            triggers.frame_loop_initialization_flag.value = True

        self._await_initialization_flag_reset()

    def await_cameras_ready(self):
        logger.trace("Waiting for all cameras to be ready...")
        while not all([triggers.camera_ready_flag.value for triggers in
                       self.frame_loop_flags.values()]) and self.should_continue:
            wait_10ms()
        logger.debug("All cameras are ready!")

    def await_new_multi_frame_available(self):
        while (not self.frames_retrieved or not self.new_multi_frame_available) and self.should_continue:
            wait_100us()
        self.new_multi_frame_available_flag.value = True

    def set_multi_frame_pulled_from_shm(self):
        for triggers in self.frame_loop_flags.values():
            triggers.new_frame_available_flag.value = False
        self.new_multi_frame_available_flag.value = False

    def _await_initialization_flag_reset(self):
        logger.trace("Initial triggers set - waiting for all triggers to reset...")
        while any([triggers.frame_loop_initialization_flag.value for triggers in
                   self.frame_loop_flags.values()]) and self.should_continue:
            wait_1ms()
        logger.trace("Initial triggers reset - Cameras ready to roll!")

    def _await_frames_grabbed(self):
        while not self.frames_grabbed and self.should_continue:
            wait_100us()

    def _await_mf_copied_from_shm(self):
        while self.new_multi_frame_available_flag.value and self.should_continue:
            wait_100us()

    def _fire_grab_trigger(self):
        logger.loop("Triggering all cameras to `grab` a frame...")
        for camera_id, triggers in self.frame_loop_flags.items():
            triggers.should_grab_frame_flag.value = True

    def _fire_retrieve_trigger(self):
        logger.loop("Triggering all cameras to `retrieve` that frame...")

        for camera_id, triggers in self.frame_loop_flags.items():
            triggers.should_retrieve_frame_flag.value = True

    def _wait_for_frames_grabbed_triggers_reset(self):
        while self.frames_grabbed and self.should_continue:
            wait_100us()

    def _wait_for_retrieve_triggers_reset(self):
        while self.frames_retrieved and self.should_continue:
            wait_100us()

    def _ensure_cameras_ready(self):
        if not self.cameras_ready:
            raise AssertionError("Not all cameras are ready!")

    def _verify_hunky_dory_after_read(self):
        if self.should_continue:
            if not self.cameras_ready:
                raise AssertionError("Not all cameras are ready!")

            if not self.frames_grabbed:
                raise AssertionError("`grab` triggers not reset!")

            if not self.frames_retrieved:
                raise AssertionError("`retrieve` triggers not reset!")

            any_new = any(
                [triggers.new_frame_available_flag.value for triggers in self.frame_loop_flags.values()]
            )
            if self.new_multi_frame_available or any_new:
                raise AssertionError(
                    f"New frames available trigger not reset properly? `new_frame_available_trigger`: {self.new_multi_frame_available}, `any_new`: {any_new}")
