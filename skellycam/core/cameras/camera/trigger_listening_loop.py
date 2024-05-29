import logging
import multiprocessing

import cv2

from skellycam.core.cameras.camera.camera_triggers import CameraTriggers
from skellycam.core.cameras.camera.get_frame import get_frame
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


def run_trigger_listening_loop(
        config: CameraConfig,
        cv2_video_capture: cv2.VideoCapture,
        camera_shared_memory: CameraSharedMemory,
        triggers: CameraTriggers,
        exit_event: multiprocessing.Event,
):
    triggers.await_initial_trigger()
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
    frame_number = 0

    # Trigger listening loop
    while not exit_event.is_set():
        wait_1ms()
        logger.loop(f"Camera {config.camera_id} ready to get next frame")
        frame_number = get_frame(
            camera_id=config.camera_id,
            cap=cv2_video_capture,
            camera_shared_memory=camera_shared_memory,
            frame_number=frame_number,
            triggers=triggers,
        )
