from typing import Dict

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_triggers import CameraTriggers, logger
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.utilities.wait_functions import wait_1us, wait_1ms, wait_10ms


class CameraGroupOrchestrator(BaseModel):
    camera_triggers: Dict[CameraId, CameraTriggers]

    ##############################################################################################################
    def trigger_multi_frame_read(self):
        # 0 - Make sure all cameras are ready
        logger.info("Step# 0 - Make sure all cameras are ready")
        self._ensure_cameras_ready()
        logger.info("All cameras are ready!")
        # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
        logger.info("Step# 1 - Fire grab triggers")
        self._fire_grab_trigger()
        logger.info("GRAB triggers fired!")

        # 2 - wait for all cameras to grab a frame
        logger.info("Step# 2 - Wait for all cameras to GRAB a frame")
        self._await_frames_grabbed()
        logger.info("All cameras have GRABbed a frame!")

        # 3- Trigger each camera to retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
        logger.info("Step# 3 - Fire retrieve triggers")
        self._fire_retrieve_trigger()
        logger.info("RETRIEVE triggers fired!")

        # 4 - wait for all cameras to retrieve the frame,
        logger.info("Step# 4 - Wait for new frames to be available")
        self.await_new_frames_available()
        logger.info("New frames are available!")

        # 5 - wait for the frame to be copied from the `write` buffer to the `read` buffer
        logger.info("Step# 5 - Wait for all frames to be copied")
        self._await_frames_copied()
        logger.info("All frames have been copied!")

        # 6 - Make sure all the triggers are as they should be
        logger.info("Step# 6 - Verify that everything is hunky-dory after reading the frames")
        self._verify_hunky_dory_after_read()
        logger.info("Everything is hunky-dory after reading the frames!")

    ##############################################################################################################

    @classmethod
    def from_camera_configs(cls, camera_configs: CameraConfigs):
        return cls(
            single_camera_triggers={
                camera_id: CameraTriggers.from_camera_id(camera_config.camera_id)
                for camera_id, camera_config in camera_configs.items()
            }
        )

    @property
    def cameras_ready(self):
        return all([triggers.camera_ready_event.is_set() for triggers in self.camera_triggers.values()])

    @property
    def new_frames_available(self):
        return all([triggers.new_frame_available_trigger.is_set() for triggers in self.camera_triggers.values()])

    @property
    def frames_grabbed(self):
        return not any([triggers.grab_frame_trigger.is_set() for triggers in self.camera_triggers.values()])

    @property
    def frames_retrieved(self):
        return not any([triggers.retrieve_frame_trigger.is_set() for triggers in self.camera_triggers.values()])

    def fire_initial_triggers(self):
        self._ensure_cameras_ready()

        logger.debug(f"Firing initial triggers for all cameras...")
        for triggers in self.camera_triggers.values():
            triggers.initial_trigger.set()

        self._await_initial_triggers_reset()

    def _await_initial_triggers_reset(self):
        logger.trace("Initial triggers set - waiting for all triggers to reset...")
        while any([triggers.initial_trigger.is_set() for triggers in self.camera_triggers.values()]):
            wait_1ms()
        logger.trace("Initial triggers reset!")

    def wait_for_cameras_ready(self):
        logger.trace("Waiting for all cameras to be ready...")
        while not all([triggers.camera_ready_event.is_set() for triggers in self.camera_triggers.values()]):
            wait_10ms()
        logger.debug("All cameras are ready!")

    def await_new_frames_available(self):
        while not self.frames_retrieved or not self.new_frames_available:
            wait_1us()
        self._clear_retrieve_frames_triggers()

    def set_frames_copied(self):
        for triggers in self.camera_triggers.values():
            triggers.set_frame_copied()

    def _await_frames_grabbed(self):
        while not self.frames_grabbed:
            wait_1us()

    def _clear_retrieve_frames_triggers(self):
        for triggers in self.camera_triggers.values():
            triggers.retrieve_frame_trigger.clear()

    def _await_frames_copied(self):
        while self.new_frames_available:
            wait_1us()
        self._clear_retrieve_frames_triggers()

    def _fire_grab_trigger(self):
        logger.loop("Triggering all cameras to `grab` a frame...")
        for camera_id, triggers in self.camera_triggers.items():
            triggers.grab_frame_trigger.set()

    def _fire_retrieve_trigger(self):
        logger.loop("Triggering all cameras to `retrieve` that frame...")

        for camera_id, triggers in self.camera_triggers.items():
            triggers.retrieve_frame_trigger.set()

    def _wait_for_frames_grabbed_triggers_reset(self):
        while self.frames_grabbed:
            wait_1us()

    def _wait_for_retrieve_triggers_reset(self):
        while self.frames_retrieved:
            wait_1us()

    def _ensure_cameras_ready(self):
        if not self.cameras_ready:
            raise AssertionError("Not all cameras are ready!")

    def _verify_hunky_dory_after_read(self):
        if not self.cameras_ready:
            raise AssertionError("Not all cameras are ready!")

        if not self.frames_grabbed:
            raise AssertionError("`grab` triggers not reset!")

        if not self.frames_retrieved:
            raise AssertionError("`retrieve` triggers not reset!")

        any_new = any(
            [triggers.new_frame_available_trigger.is_set() for triggers in self.camera_triggers.values()]
        )
        if self.new_frames_available or any_new:
            raise AssertionError("New frames available trigger not reset!")
