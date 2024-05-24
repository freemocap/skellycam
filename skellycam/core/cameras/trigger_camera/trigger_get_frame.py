import logging
import multiprocessing
import time

import cv2

from skellycam.core import CameraId
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


def get_frame(camera_id: CameraId,
              camera_shared_memory: CameraSharedMemory,
              cap: cv2.VideoCapture,
              frame: FramePayload,
              triggers: SingleCameraTriggers,
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
    triggers.await_grab_trigger()
    logger.loop(f"Camera {camera_id} received `grab` trigger - calling `cv2.VideoCapture.grab()`")

    # frame.timestamps.pre_grab_timestamp = time.perf_counter_ns()
    # decouple `grab` and `retrieve` for better sync -
    # https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146

    grab_success = cap.grab()  # grab the frame from the camera, but don't decode it yet
    # frame.timestamps.post_grab_timestamp = time.perf_counter_ns()

    if grab_success:
        triggers.set_frame_grabbed()
    else:
        raise ValueError(f"Failed to grab frame from camera {camera_id}")

    # frame.timestamps.wait_for_retrieve_trigger_timestamp = time.perf_counter_ns()

    triggers.await_retrieve_trigger()

    # frame.timestamps.pre_retrieve_timestamp = time.perf_counter_ns()
    retrieve_success, image = cap.retrieve()  # decode the frame into an image
    # frame.timestamps.post_retrieve_return = time.perf_counter_ns()
    frame.timestamp_ns = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {camera_id}")

    frame.success = grab_success and retrieve_success
    frame.image_checksum = frame.calculate_image_checksum(image)
    frame.image_shape = image.shape
    camera_shared_memory.put_new_frame(
        frame=frame,
        image=image,
    )
    return FramePayload.from_previous(frame)

