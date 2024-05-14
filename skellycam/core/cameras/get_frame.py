import logging
import multiprocessing
import time

import cv2

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


def get_frame(camera_id: CameraId,
              camera_shared_memory: CameraSharedMemory,
              cap: cv2.VideoCapture,
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
    logger.loop(f"Camera {camera_id} received `grab` trigger - calling `cv2.VideoCapture.grab()`")

    # frame.timestamps.pre_grab_timestamp = time.perf_counter_ns()
    # decouple `grab` and `retrieve` for better sync -
    # https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146

    grab_success = cap.grab()  # grab the frame from the camera, but don't decode it yet
    # frame.timestamps.post_grab_timestamp = time.perf_counter_ns()

    if grab_success:
        frame_grabbed_trigger.set()
    else:
        raise ValueError(f"Failed to grab frame from camera {camera_id}")

    # frame.timestamps.wait_for_retrieve_trigger_timestamp = time.perf_counter_ns()

    while not retrieve_frame_trigger.is_set():
        if next_frame is None:
            next_frame = FramePayload.from_previous(frame)  # create next frame in presumed downtime
        time.sleep(0.0001)  # gotta go fast

    logger.loop(f"Camera {camera_id} received `retrieve` trigger - calling `cv2.VideoCapture.retrieve()`")

    # frame.timestamps.pre_retrieve_timestamp = time.perf_counter_ns()
    retrieve_success, image = cap.retrieve()  # decode the frame into an image
    # frame.timestamps.post_retrieve_return = time.perf_counter_ns()
    frame.timestamp_ns = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {camera_id}")

    frame.success = grab_success and retrieve_success
    frame.image_checksum = frame.calculate_image_checksum(image)
    frame.image_shape = image.shape
    camera_shared_memory.put_frame(
        frame=frame,
        image=cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
    )
    next_frame.previous_frame_timestamp_ns = frame.timestamp_ns

    return next_frame
