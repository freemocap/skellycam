import logging
import multiprocessing
import time

import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
from skellycam.core.cameras.trigger_camera.trigger_get_frame import get_frame
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory
from skellycam.system.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


def run_trigger_listening_loop(config: CameraConfig,
                               cv2_video_capture: cv2.VideoCapture,
                               camera_shared_memory: CameraSharedMemory,
                               triggers: SingleCameraTriggers,
                               exit_event: multiprocessing.Event):
    triggers.await_initial_trigger()
    frame = FramePayload.create_initial_frame(camera_id=config.camera_id,
                                              image_shape=config.image_shape)
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")

    while not exit_event.is_set():
        wait_1ms()
        logger.loop(f"Camera {config.camera_id} ready to get next frame")
        frame = get_frame(camera_id=config.camera_id,
                          cap=cv2_video_capture,
                          camera_shared_memory=camera_shared_memory,
                          frame=frame,
                          triggers=triggers,
                          )
        triggers.clear_frame_triggers()

    logger.trace(f"Camera {config.camera_id} trigger listening loop exited")
