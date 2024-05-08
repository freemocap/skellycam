import logging
import multiprocessing
import time
from typing import Optional

import cv2
import numpy as np

from skellycam.core import CameraId
from skellycam.core.cameras.config.apply_config import apply_camera_configuration
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.create_cv2_video_capture import create_cv2_capture
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


class TriggerCameraProcess:
    def __init__(self,
                 config: CameraConfig,
                 shared_memory_name: str,
                 lock: multiprocessing.Lock,
                 grab_frame_trigger: multiprocessing.Event,
                 frame_grabbed_trigger: multiprocessing.Event,
                 retrieve_frame_trigger: multiprocessing.Event,
                 ready_event: multiprocessing.Event,
                 exit_event: multiprocessing.Event,
                 ):
        self._config = config

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_name,
                                                      lock,
                                                      grab_frame_trigger,
                                                      frame_grabbed_trigger,
                                                      retrieve_frame_trigger,
                                                      ready_event,
                                                      exit_event
                                                      )
                                                )

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_name: str,
                     lock: multiprocessing.Lock,
                     grab_frame_trigger: multiprocessing.Event,
                     frame_grabbed_trigger: multiprocessing.Event,
                     retrieve_frame_trigger: multiprocessing.Event,
                     ready_event: multiprocessing.Event,
                     exit_event: multiprocessing.Event):
        logger.debug(f"Camera {config.camera_id} process started")
        camera_shared_memory = CameraSharedMemory.from_config(camera_config=config,
                                                              lock=lock,
                                                              shared_memory_name=shared_memory_name)
        cv2_video_capture = create_cv2_capture(config)
        apply_camera_configuration(cv2_video_capture, config)
        run_trigger_listening_loop(config=config,
                                   cv2_video_capture=cv2_video_capture,
                                   camera_shared_memory=camera_shared_memory,
                                   grab_frame_trigger=grab_frame_trigger,
                                   frame_grabbed_trigger=frame_grabbed_trigger,
                                   retrieve_frame_trigger=retrieve_frame_trigger,
                                   ready_event=ready_event,
                                   exit_event=exit_event)
        cv2_video_capture.release()
        logger.debug(f"Camera {config.camera_id} process completed")

    def start(self):
        self._process.start()


def run_trigger_listening_loop(config: CameraConfig,
                               cv2_video_capture: cv2.VideoCapture,
                               camera_shared_memory: CameraSharedMemory,
                               grab_frame_trigger: multiprocessing.Event,
                               frame_grabbed_trigger: multiprocessing.Event,
                               retrieve_frame_trigger: multiprocessing.Event,
                               ready_event: multiprocessing.Event,
                               exit_event: multiprocessing.Event):
    frame_number = 0
    frame: Optional[FramePayload] = None

    ready_event.set()
    await_initial_trigger(config, grab_frame_trigger)
    frame = FramePayload.create_empty(camera_id=config.camera_id, frame_number=frame_number)

    while not exit_event.is_set():
        time.sleep(0.001)

        if grab_frame_trigger.is_set():
            frame = get_frame(camera_id=config.camera_id,
                              cv2_video_capture=cv2_video_capture,
                              camera_shared_memory=camera_shared_memory,
                              frame=frame,
                              frame_number=frame_number,
                              frame_grabbed_trigger=frame_grabbed_trigger,
                              retrieve_frame_trigger=retrieve_frame_trigger,
                              )
            frame_number += 1
            retrieve_frame_trigger.clear()
            frame_grabbed_trigger.clear()
            grab_frame_trigger.clear()

    logger.trace(f"Trigger listening loop for camera {config.camera_id} completed")


def await_initial_trigger(config, grab_frame_trigger: multiprocessing.Event):
    while not grab_frame_trigger.is_set():
        time.sleep(0.001)
    time.sleep(0.1)
    grab_frame_trigger.clear()
    logger.trace(f"Initial frame trigger received for camera {config.camera_id}!"
                 f" - Resetting trigger and prepared to read frames...")


def get_frame(camera_id: CameraId,
              camera_shared_memory: CameraSharedMemory,
              cv2_video_capture: cv2.VideoCapture,
              frame: FramePayload,
              frame_number: int,
              frame_grabbed_trigger: multiprocessing.Event,
              retrieve_frame_trigger: multiprocessing.Event,
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
    next_frame = None

    # frame.timestamps.pre_grab_timestamp = time.perf_counter_ns()
    # decouple `grab` and `retrieve` for better sync - https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146
    grab_success = cv2_video_capture.grab()  # grab the frame from the camera, but don't decode it yet
    # frame.timestamps.post_grab_timestamp = time.perf_counter_ns()

    if grab_success:
        frame_grabbed_trigger.set()
    else:
        raise ValueError(f"Failed to grab frame from camera {camera_id}")

    # frame.timestamps.wait_for_retrieve_trigger_timestamp = time.perf_counter_ns()

    while not retrieve_frame_trigger.is_set():
        if next_frame is None:
            next_frame = FramePayload.create_empty(camera_id=camera_id,
                                                   frame_number=frame_number + 1)  # create next frame in presumed downtime
        time.sleep(0.0001)  # 0.1ms

    # frame.timestamps.pre_retrieve_timestamp = time.perf_counter_ns()
    retrieve_success, image = cv2_video_capture.retrieve()  # decode the frame into an image
    # frame.timestamps.post_retrieve_return = time.perf_counter_ns()
    frame.timestamp_ns = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {camera_id}")

    frame.success = grab_success and retrieve_success
    frame.image_checksum = frame.calculate_checksum(image)
    frame.image_shape = image.shape
    camera_shared_memory.put_frame(
        frame=frame,
        image=cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
    )
    next_frame.previous_frame_timestamp_ns = frame.timestamp_ns

    return next_frame
