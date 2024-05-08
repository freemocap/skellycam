import logging
import multiprocessing
import time

import cv2

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
                 initial_trigger: multiprocessing.Event,
                 grab_frame_trigger: multiprocessing.Event,
                 frame_grabbed_trigger: multiprocessing.Event,
                 retrieve_frame_trigger: multiprocessing.Event,
                 camera_ready_event: multiprocessing.Event,
                 exit_event: multiprocessing.Event,
                 ):
        self._config = config

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_name,
                                                      lock,
                                                      initial_trigger,
                                                      grab_frame_trigger,
                                                      frame_grabbed_trigger,
                                                      retrieve_frame_trigger,
                                                      camera_ready_event,
                                                      exit_event
                                                      )
                                                )

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_name: str,
                     lock: multiprocessing.Lock,
                     initial_trigger: multiprocessing.Event,
                     grab_frame_trigger: multiprocessing.Event,
                     frame_grabbed_trigger: multiprocessing.Event,
                     retrieve_frame_trigger: multiprocessing.Event,
                     camera_ready_event: multiprocessing.Event,
                     exit_event: multiprocessing.Event):
        logger.debug(f"Camera {config.camera_id} process started")
        camera_shared_memory = CameraSharedMemory.from_config(camera_config=config,
                                                              lock=lock,
                                                              shared_memory_name=shared_memory_name)
        cv2_video_capture = create_cv2_capture(config)
        apply_camera_configuration(cv2_video_capture, config)
        camera_ready_event.set()
        run_trigger_listening_loop(config=config,
                                   cv2_video_capture=cv2_video_capture,
                                   camera_shared_memory=camera_shared_memory,
                                   initial_trigger=initial_trigger,
                                   grab_frame_trigger=grab_frame_trigger,
                                   frame_grabbed_trigger=frame_grabbed_trigger,
                                   retrieve_frame_trigger=retrieve_frame_trigger,
                                   exit_event=exit_event)
        cv2_video_capture.release()
        logger.debug(f"Camera {config.camera_id} process completed")

    def start(self):
        self._process.start()


def run_trigger_listening_loop(config: CameraConfig,
                               cv2_video_capture: cv2.VideoCapture,
                               camera_shared_memory: CameraSharedMemory,
                               initial_trigger: multiprocessing.Event,
                               grab_frame_trigger: multiprocessing.Event,
                               frame_grabbed_trigger: multiprocessing.Event,
                               retrieve_frame_trigger: multiprocessing.Event,
                               exit_event: multiprocessing.Event):
    await_initial_trigger(config, initial_trigger=initial_trigger)
    frame = FramePayload.create_empty(camera_id=config.camera_id, frame_number=0)
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
    while not exit_event.is_set():
        time.sleep(0.001)
        logger.trace(f"Camera {config.camera_id} read to get next frame")
        frame = get_frame(camera_id=config.camera_id,
                          cv2_video_capture=cv2_video_capture,
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


def get_frame(camera_id: CameraId,
              camera_shared_memory: CameraSharedMemory,
              cv2_video_capture: cv2.VideoCapture,
              frame: FramePayload,
              grab_frame_trigger: multiprocessing.Event,
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
    while not grab_frame_trigger.is_set():
        time.sleep(0.0001)
    logger.trace(f"Camera {camera_id} received `grab` trigger - calling `cv2.VideoCapture.grab()`")

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
                                                   frame_number=frame.frame_number + 1)  # create next frame in presumed downtime
        time.sleep(0.0001)  # 0.1ms
    logger.trace(f"Camera {camera_id} received `retrieve` trigger - calling `cv2.VideoCapture.retrieve()`")

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
