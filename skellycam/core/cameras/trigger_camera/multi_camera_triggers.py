import time
from typing import Dict

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers, logger


class MultiCameraTriggers(BaseModel):
    single_camera_triggers: Dict[CameraId, SingleCameraTriggers]

    ######################
    ######################
    def trigger_multi_frame_read(self, loop_wait_time: float = 0.0001):
        self._ensure_cameras_ready()
        # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
        logger.loop("Triggering all cameras to `grab` a frame...")
        for camera_id, grab_frame_trigger in self.grab_frame_triggers.items():
            if grab_frame_trigger.is_set():
                raise ValueError(f"Triggering `grab` from camera_id: {camera_id}, but trigger is already set - this should not happen!")
            grab_frame_trigger.set()

        # 2 - wait for all cameras to grab a frame
        while not all([frame_grabbed_trigger.is_set() for frame_grabbed_trigger in self.frame_grabbed_triggers.values()]):
            time.sleep(loop_wait_time)

        # 3- Trigger each camera should retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
        logger.loop("Triggering all cameras to `retrieve` that frame...")
        for camera_id, retrieve_frame_triggers in self.retrieve_frame_triggers.items():
            if retrieve_frame_triggers.is_set():
                raise ValueError(f"Triggering `retrieve` from camera_id: {camera_id}, but trigger is already set - this should not happen!")
            retrieve_frame_triggers.set()
    ######################
    ######################

    @classmethod
    def from_camera_configs(cls, camera_configs: CameraConfigs):
        return cls(
            single_camera_triggers={camera_id: SingleCameraTriggers.from_camera_config(camera_config)
                                    for camera_id, camera_config in camera_configs.items()}
        )

    @property
    def cameras_ready(self):
        return all([triggers.camera_ready_event.is_set()
                    for triggers in self.single_camera_triggers.values()])

    def _ensure_cameras_ready(self):
        if not self.cameras_ready:
            raise AssertionError("Not all cameras are ready!")

    def wait_for_cameras_ready(self, loop_wait_time: float = 1.0):
        while not all([camera_ready_event.is_set() for camera_ready_event in self.camera_ready_events.values()]):
            logger.trace("Waiting for all cameras to be ready...")
            time.sleep(loop_wait_time)
            for camera_id, camera_ready_event in self.camera_ready_events.items():
                if camera_ready_event.is_set():
                    logger.debug(f"Camera {camera_id} is ready!")

        logger.debug("All cameras are ready!")
    def send_initial_triggers(self, wait_loop_time: float = 0.01):

        self._ensure_cameras_ready()

        logger.debug(f"sending initial trigger event to cameras")
        for initial_trigger in self.initial_triggers.values():
            initial_trigger.set()
        while any([initial_trigger.is_set() for initial_trigger in self.initial_triggers.values()]):
            time.sleep(wait_loop_time)
        logger.trace("Initial triggers sent and reset - starting multi-camera read loop...")

    def wait_for_grab_triggers_reset(self, wait_loop_time: float = 0.001):
        logger.loop("Waiting for all `grab` triggers to reset...")
        while not all([not trigger.is_set() for trigger in self.grab_frame_triggers.values()]):
            time.sleep(wait_loop_time)
