import logging
import multiprocessing
from dataclasses import dataclass
from typing import Dict

from skellycam.app.app_controller.ipc_flags import IPCFlags
from skellycam.core import CameraId
from skellycam.core.camera_group.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.utilities.wait_functions import wait_10ms, wait_100ms, wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class CameraGroupOrchestrator:
    frame_loop_flags: Dict[CameraId, CameraFrameLoopFlags]
    ipc_flags: IPCFlags

    pause_when_able: multiprocessing.Value
    frame_loop_paused: multiprocessing.Value

    should_pull_multi_frame_from_shm: multiprocessing.Value = multiprocessing.Value("b", False)

    loop_count: int = 0

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
            ipc_flags=ipc_flags,
            pause_when_able=multiprocessing.Value("b", False),
            frame_loop_paused=multiprocessing.Value("b", False),
        )

    @property
    def camera_ids(self):
        return list(self.frame_loop_flags.keys())

    @property
    def should_continue(self):
        return not self.ipc_flags.kill_camera_group_flag.value and not self.ipc_flags.global_kill_flag.value

    @property
    def cameras_ready(self):
        self.ipc_flags.cameras_connected_flag.value = all(
            [triggers.camera_ready_flag.value for triggers in self.frame_loop_flags.values()])
        return self.ipc_flags.cameras_connected_flag.value

    @property
    def new_multi_frame_available(self):
        return all([triggers.new_frame_in_shm.value for triggers in self.frame_loop_flags.values()])

    @property
    def frames_grabbed(self):
        return not any([triggers.should_grab_frame_flag.value for triggers in self.frame_loop_flags.values()])

    @property
    def frames_retrieved(self):
        return not any([triggers.should_retrieve_frame_flag.value for triggers in self.frame_loop_flags.values()])

    def pause_loop(self):
        self.pause_when_able.value = True
        while not self.frame_loop_paused.value:
            wait_10ms()
        logger.trace("Frame loop paused.")

    def unpause_loop(self):
        self.pause_when_able.value = False
        while self.frame_loop_paused.value:
            wait_10ms()
        logger.trace("Frame loop un-paused.")

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
            else:
                return  # Exit if we should not continue

        # 0 - Make sure all cameras are ready
        logger.loop(f"FRAME  {self.loop_count} LOOP BEGIN")
        self._ensure_cameras_ready()
        wait_1ms()

        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #0 (start)  - Send frame read initialization triggers")
        self.send_initialization_signal()
        wait_1ms()
        self._await_initialization_flag_reset()
        wait_1ms()
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #0 (finish) - All cameras are ready to go!")

        # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #1 (start) - Fire grab triggers")
        self._send_should_grab_frame_signal()
        wait_1ms()
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #1 (finish) - GRAB triggers fired!")

        # 2 - wait for all cameras to grab a frame
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #2 (start) - Wait for all cameras to GRAB a frame")
        self._await_frames_grabbed()
        wait_1ms()
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #2 (finish) - All cameras have GRABbed a frame!")

        # 3- Trigger each camera to retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #3 (start)- Fire retrieve triggers")
        self._send_should_retrieve_frame_signal()
        wait_1ms()
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #3 (finish) - RETRIEVE triggers fired!")

        # 4 - wait for all cameras to retrieve the frame
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #4 (start) - Wait for all cameras to RETRIEVE the frame")
        self._await_frames_retrieved()
        wait_1ms()
        logger.loop(
            f"**Frame Loop#{self.loop_count}** - Step #4 (finish) - All cameras have RETRIEVED the frame!")

        # 5 - Trigger should copy frame into shared memory
        logger.loop(
            f"**Frame Loop#{self.loop_count}** - Step #5 (start) - Signaling should copy multi-frame into shared memory")
        self._signal_should_put_frame_into_shm()
        wait_1ms()
        logger.loop(
            f"**Frame Loop#{self.loop_count}** - Step #5 (finish) - Signaled should copy multi-frame into shared memory!")

        self._signal_should_pull_multi_frame_from_shm()
        wait_1ms()

        # 6 - wait for the frame to be copied from the `write` buffer to the `read` buffer
        logger.loop(
            f"**Frame Loop#{self.loop_count}** - Step #6 (start) - Wait for multi-frame to be copied from shared memory")
        self._await_multi_frame_pulled_from_shm()
        wait_1ms()
        logger.loop(f"**Frame Loop#{self.loop_count}** - Step #6 (finish) - Multi-frame copied from shared memory!")

        # 7 - Make sure all the triggers are as they should be
        logger.loop(
            f"**Frame Loop#{self.loop_count}** - Step# 7 (start) - Verify that everything is hunky-dory after reading the frames")
        self._verify_hunky_dory_after_read()
        wait_1ms()
        logger.loop(
            f"**Frame Loop#{self.loop_count}** - Step #7 (end) - Everything is hunky-dory after reading the frames!")
        logger.loop(f"FRAME LOOP# {self.loop_count} Complete!")
        self.loop_count += 1

    ##############################################################################################################

    def send_initialization_signal(self):

        logger.loop(f"Firing initial triggers for all cameras...")
        for triggers in self.frame_loop_flags.values():
            triggers.frame_read_initialization_flag.value = True

    def await_cameras_ready(self):
        logger.trace("Waiting for all cameras to be ready...")
        while not all([triggers.camera_ready_flag.value for triggers in
                       self.frame_loop_flags.values()]) and self.should_continue:
            wait_10ms()
        logger.debug("All cameras are ready!")

    def signal_multi_frame_pulled_from_shm(self):
        for triggers in self.frame_loop_flags.values():
            triggers.new_frame_in_shm.value = False
        wait_1ms()  # Give it a moment before final reset of this frame loop
        self.should_pull_multi_frame_from_shm.value = False

    def _await_initialization_flag_reset(self):
        logger.loop("Initial triggers set - waiting for all triggers to reset...")
        while any([flags.frame_read_initialization_flag.value for flags in
                   self.frame_loop_flags.values()]) and self.should_continue:
            wait_1ms()

    def _await_frames_grabbed(self):
        while not self.frames_grabbed and self.should_continue:
            wait_1ms()

    def _await_multi_frame_pulled_from_shm(self):
        while self.should_pull_multi_frame_from_shm.value and self.should_continue:
            wait_1ms()

    def _send_should_grab_frame_signal(self):
        logger.loop("Triggering all cameras to `grab` a frame...")
        for camera_id, flags in self.frame_loop_flags.items():
            flags.should_grab_frame_flag.value = True

    def _send_should_retrieve_frame_signal(self):
        logger.loop("Triggering all cameras to `retrieve` that frame...")

        for camera_id, flags in self.frame_loop_flags.items():
            flags.should_retrieve_frame_flag.value = True

    def _signal_should_put_frame_into_shm(self):
        logger.loop("Triggering all cameras to copy the frame into shared memory...")
        for camera_id, flags in self.frame_loop_flags.items():
            flags.should_copy_frame_into_shm_flag.value = True

    def _signal_should_pull_multi_frame_from_shm(self):
        logger.loop("Signaling that the multi-frame is ready to be pulled from shared memory...")
        self.should_pull_multi_frame_from_shm.value = True

    def _await_frames_retrieved(self):
        while not self.frames_retrieved and self.should_continue:
            wait_1ms()

    def _ensure_cameras_ready(self):
        if not self.cameras_ready:
            raise AssertionError("Not all cameras are ready!")

    def _verify_hunky_dory_after_read(self, max_attempts=5):
        are_cameras_ready = False
        are_frame_grab_flags_reset = False
        are_frame_retrieve_flags_reset = False
        is_multi_frame_pulled_from_shm_reset = False
        are_camera_new_frame_available_flags_reset = False
        for attempt_number in range(max_attempts):
            if self.should_continue:
                are_cameras_ready = self.cameras_ready
                are_frame_grab_flags_reset = self.frames_grabbed
                are_frame_retrieve_flags_reset = self.frames_retrieved
                is_multi_frame_pulled_from_shm_reset = not self.should_pull_multi_frame_from_shm.value
                are_camera_new_frame_available_flags_reset = not any(
                    [flags.new_frame_in_shm.value for flags in self.frame_loop_flags.values()])

                if all([are_cameras_ready,
                        are_frame_grab_flags_reset,
                        are_frame_retrieve_flags_reset,
                        is_multi_frame_pulled_from_shm_reset,
                        are_camera_new_frame_available_flags_reset]):
                    logger.loop(f"Frame loop verification passed on attempt#{attempt_number + 1} of {max_attempts}")
                    return  # All good, break out of loop

                logger.warning(f"Frame loop verification failed on attempt {attempt_number + 1} - retrying...")
                wait_1ms()

        raise AssertionError(f"Frame loop verification failed after {max_attempts} attempts -[\n"
                             f"are_cameras_ready: {are_cameras_ready}, \n"
                             f"are_frame_grab_flags_reset: {are_frame_grab_flags_reset}, \n"
                             f"are_frame_retrieve_flag_reset: {are_frame_retrieve_flags_reset}, \n"
                             f"is_multi_frame_pulled_from_shm_flag_reset: {is_multi_frame_pulled_from_shm_reset}, \n"
                             f"are_camera_new_frame_available_flags_reset: {are_camera_new_frame_available_flags_reset}]\n")
