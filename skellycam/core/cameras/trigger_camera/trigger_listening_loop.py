import logging
import multiprocessing
import time

import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.trigger_camera.get_frame import get_frame
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


def run_trigger_listening_loop(config: CameraConfig,
                               cv2_video_capture: cv2.VideoCapture,
                               camera_shared_memory: CameraSharedMemory,
                               initial_trigger: multiprocessing.Event,
                               grab_frame_trigger: multiprocessing.Event,
                               frame_grabbed_trigger: multiprocessing.Event,
                               retrieve_frame_trigger: multiprocessing.Event,
                               exit_event: multiprocessing.Event):
    await_initial_trigger(config, initial_trigger=initial_trigger)
    frame = FramePayload.create_empty(camera_id=config.camera_id,
                                      image_shape=config.image_shape,
                                      frame_number=0)
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
    while not exit_event.is_set():
        time.sleep(0.001)
        logger.loop(f"Camera {config.camera_id} ready to get next frame")
        frame = get_frame(camera_id=config.camera_id,
                          cap=cv2_video_capture,
                          camera_shared_memory=camera_shared_memory,
                          frame=frame,
                          grab_frame_trigger=grab_frame_trigger,
                          frame_grabbed_trigger=frame_grabbed_trigger,
                          retrieve_frame_trigger=retrieve_frame_trigger,
                          )
        retrieve_frame_trigger.clear()
        frame_grabbed_trigger.clear()
        grab_frame_trigger.clear()

    logger.trace(f"Camera {config.camera_id} trigger listening loop exited")


def await_initial_trigger(config, initial_trigger: multiprocessing.Event):
    while not initial_trigger.is_set():
        time.sleep(0.01)
    logger.trace(f"Camera {config.camera_id} process received `initial_trigger`")
    initial_trigger.clear()
