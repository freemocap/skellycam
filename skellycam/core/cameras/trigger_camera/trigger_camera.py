import asyncio
import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import Optional, List

import cv2

from skellycam.core.cameras.config.apply_config import apply_camera_configuration
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.create_cv2_video_capture import create_cv2_capture
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.shared_image_memory import SharedPayloadMemoryManager

logger = logging.getLogger(__name__)


class TriggerCameraProcess:
    def __init__(self,
                 config: CameraConfig,
                 frame_queue: multiprocessing.Queue,  # send-only multiprocessing.Queue
                 config_update_queue: multiprocessing.Queue,  # send-only multiprocessing.Queue
                 all_camera_ids: List[CameraId],
                 shared_memory_name: str,
                 get_frame_trigger: multiprocessing.Event,
                 ready_event: multiprocessing.Event,
                 exit_event: multiprocessing.Event,
                 ):
        self._config = config

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_name,
                                                      all_camera_ids,
                                                      frame_queue,
                                                      config_update_queue,
                                                      get_frame_trigger,
                                                      ready_event,
                                                      exit_event
                                                      )
                                                )

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_name: str,
                     all_camera_ids: List[CameraId],
                     frame_queue: multiprocessing.Queue,
                     config_update_queue: multiprocessing.Queue,
                     get_frame_trigger: multiprocessing.Event,
                     ready_event: multiprocessing.Event,
                     exit_event: multiprocessing.Event):
        logger.debug(f"Camera {config.camera_id} process started")
        existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
        shared_memory_manager = SharedPayloadMemoryManager(camera_ids=all_camera_ids,
                                                           image_resolution=config.resolution,
                                                           existing_shared_memory=existing_shared_memory)
        cv2_video_capture = create_cv2_capture(config)
        apply_camera_configuration(cv2_video_capture, config)
        run_trigger_listening_loop(config=config,
                                   cv2_video_capture=cv2_video_capture,
                                   shared_memory_manager=shared_memory_manager,
                                   frame_queue=frame_queue,
                                   config_update_queue=config_update_queue,
                                   get_frame_trigger=get_frame_trigger,
                                   ready_event=ready_event,
                                   exit_event=exit_event)
        cv2_video_capture.release()
        logger.debug(f"Camera {config.camera_id} process completed")

    def start(self):
        self._process.start()


def run_trigger_listening_loop(config: CameraConfig,
                               cv2_video_capture: cv2.VideoCapture,
                               shared_memory_manager: SharedPayloadMemoryManager,
                               frame_queue: multiprocessing.Queue,
                               config_update_queue: multiprocessing.Queue,
                               get_frame_trigger: multiprocessing.Event,
                               ready_event: multiprocessing.Event,
                               exit_event: multiprocessing.Event):
    frame_number = 0
    frame: Optional[FramePayload] = None
    ready_event.set()
    await_initial_trigger(config, get_frame_trigger)

    while not exit_event.is_set():
        time.sleep(0.001)

        if get_frame_trigger.is_set():
            frame = get_frame(cv2_video_capture=cv2_video_capture,
                              camera_id=config.camera_id,
                              frame_number=frame_number,
                              shared_memory_manager=shared_memory_manager,
                              previous_frame_timestamp_ns=frame.timestamp_ns if frame else -1
                              )
            frame_queue.put(frame)
            frame_number += 1
            get_frame_trigger.clear()

        elif not config_update_queue.empty():
            logger.trace(f"Config update received for camera {config.camera_id}")
            ready_event.clear()
            new_config = config_update_queue.get()
            config = new_config
            if not config.use_this_camera:
                logger.debug(f"Camera {config.camera_id} `use_this_camera` set to False - stopping camera process")
                break
            apply_camera_configuration(cv2_video_capture, config)
            ready_event.set()

    logger.trace(f"Trigger listening loop for camera {config.camera_id} completed")


def await_initial_trigger(config, get_frame_trigger: multiprocessing.Event):
    while not get_frame_trigger.is_set():
        time.sleep(0.001)
    time.sleep(0.1)
    get_frame_trigger.clear()
    logger.trace(f"Initial frame trigger received for camera {config.camera_id}!"
                 f" - Resetting trigger and prepared to read frames...")


def get_frame(
        camera_id: CameraId,
        frame_number: int,
        previous_frame_timestamp_ns: int,
        shared_memory_manager: SharedPayloadMemoryManager,
        cv2_video_capture: cv2.VideoCapture,
) -> FramePayload:
    """
    THIS IS WHERE THE MAGIC HAPPENS

    This method is responsible for grabbing the next frame from the camera - it is the point of "transduction"
     when a pattern of environmental energy (i.e. a timeslice of the 2D pattern of light intensity in 3 wavelengths
      within the field of view of the camera ) is absorbed by the camera's sensor and converted into a digital
      representation of that pattern (i.e. a 2D array of pixel values in 3 channels).

    This is the empirical measurement, whereupon all future inference will derive their epistemological grounding.

    This sweet baby must be protected at all costs. Nothing is allowed to block this call (which could result in
    a frame drop)
    """
    pre_read_timestamp = time.perf_counter_ns()
    success, image = cv2_video_capture.read()  # THIS, specifically,  IS WHERE THE MAGIC HAPPENS <3
    post_read_timestamp = time.perf_counter_ns()

    if not success or image is None:
        raise ValueError(f"Failed to read frame from camera {camera_id}")

    if previous_frame_timestamp_ns == -1:
        time_since_last_frame_ns = 0
    else:
        time_since_last_frame_ns = post_read_timestamp - previous_frame_timestamp_ns

    return FramePayload.as_shared_memory(
        shared_memory_manager=shared_memory_manager,
        success=success,
        image=cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
        timestamp_ns=post_read_timestamp,
        frame_number=frame_number,
        camera_id=camera_id,
        read_duration_ns=post_read_timestamp - pre_read_timestamp,
        time_since_last_frame_ns=time_since_last_frame_ns,
    )
