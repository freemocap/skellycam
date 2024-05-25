from typing import Dict

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers, logger
from skellycam.system.utilities.wait_functions import wait_1us, wait_10ms, wait_1s


class MultiCameraTriggerOrchestrator(BaseModel):
    single_camera_triggers: Dict[CameraId, SingleCameraTriggers]

    ##############################################################################################################
    def trigger_multi_frames_read(self):
        # 0 - Make sure all cameras are ready
        self._ensure_cameras_ready()

        # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
        self._fire_grab_trigger()

        # 2 - wait for all cameras to grab a frame
        self._await_frames_grabbed()

        # 3- Trigger each camera to retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
        self._fire_retrieve_trigger()

        # 4 - wait for all cameras to retrieve the frame,
        self.await_new_frames_available()

        # 5 - wait for the frame to be copied from the `write` buffer to the `read` buffer
        self._await_frames_copied()

        # 6 - Make sure all the triggers are as they should be
        self._verify_hunky_dory_after_read()

    ##############################################################################################################

    @classmethod
    def from_camera_configs(cls, camera_configs: CameraConfigs):
        return cls(
            single_camera_triggers={camera_id: SingleCameraTriggers.from_camera_id(camera_config.camera_id)
                                    for camera_id, camera_config in camera_configs.items()}
        )

    @property
    def cameras_ready(self):
        return all([triggers.camera_ready_event.is_set()
                    for triggers in self.single_camera_triggers.values()])

    @property
    def new_frames_available(self):
        return all([triggers.new_frame_available_trigger.is_set()
                    for triggers in self.single_camera_triggers.values()])

    @property
    def frames_grabbed(self):
        return not any([triggers.grab_frame_trigger.is_set()
                        for triggers in self.single_camera_triggers.values()])

    @property
    def frames_retrieved(self):
        return not any([triggers.retrieve_frame_trigger.is_set()
                        for triggers in self.single_camera_triggers.values()])

    def fire_initial_triggers(self):

        self._ensure_cameras_ready()

        logger.debug(f"Firing initial triggers for all cameras...")
        for triggers in self.single_camera_triggers.values():
            triggers.initial_trigger.set()

        logger.trace("Initial triggers set - waiting for all triggers to reset...")
        while any([triggers.initial_trigger.is_set()
                   for triggers in self.single_camera_triggers.values()]):
            wait_10ms()
        logger.trace("Initial triggers reset!")

    def wait_for_cameras_ready(self):
        while not all([triggers.camera_ready_event.is_set() for triggers in self.single_camera_triggers.values()]):
            logger.trace("Waiting for all cameras to be ready...")
            wait_1s()
        logger.debug("All cameras are ready!")

    def await_new_frames_available(self):
        while not self.frames_retrieved or not self.new_frames_available:
            wait_1us()
        self._clear_retrieve_frames_triggers()

    def set_frames_copied(self):
        for triggers in self.single_camera_triggers.values():
            triggers.set_frame_copied()

    def _await_frames_grabbed(self):
        while not self.frames_grabbed:
            wait_1us()

    def _clear_retrieve_frames_triggers(self):
        for triggers in self.single_camera_triggers.values():
            triggers.retrieve_frame_trigger.clear()

    def _await_frames_copied(self):
        while self.new_frames_available:
            wait_1us()
        self._clear_retrieve_frames_triggers()

    def _fire_grab_trigger(self):
        logger.loop("Triggering all cameras to `grab` a frame...")
        for camera_id, triggers in self.single_camera_triggers.items():
            triggers.grab_frame_trigger.set()

    def _fire_retrieve_trigger(self):
        logger.loop("Triggering all cameras to `retrieve` that frame...")

        for camera_id, triggers in self.single_camera_triggers.items():
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
            raise AssertionError('`grab` triggers not reset!')

        if not self.frames_retrieved:
            raise AssertionError("`retrieve` triggers not reset!")

        any_new = any([triggers.new_frame_available_trigger.is_set()
                       for triggers in self.single_camera_triggers.values()])
        if self.new_frames_available or any_new:
            raise AssertionError("New frames available trigger not reset!")
