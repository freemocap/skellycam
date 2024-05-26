import logging
import time

import cv2
import numpy as np

from skellycam.core import CameraId
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


def image_metadata_to_shm_npy(camera_id: CameraId,
                              timestamp_ns: int,
                              pre_grab_timestamp: int,
                              post_grab_timestamp: int,
                              pre_retrieve_timestamp: int,
                              post_retrieve_return: int,
                              shared_memory: CameraSharedMemory,
                              ) -> np.ndarray:
    return np.ndarray([camera_id,
                       timestamp_ns,
                       pre_grab_timestamp,
                       post_grab_timestamp,
                       pre_retrieve_timestamp,
                       post_retrieve_return,
                       ],
                      dtype=np.uint64,
                      buffer=shared_memory.metadata_shm.buf)


def get_frame(camera_id: CameraId,
              frame_number: int,
              camera_shared_memory: CameraSharedMemory,
              cap: cv2.VideoCapture,
              triggers: SingleCameraTriggers,
              ) -> int:
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

    # decouple `grab` and `retrieve` for better sync -
    # https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146
    pre_grab_timestamp = time.perf_counter_ns()
    grab_success = cap.grab()  # grab the frame from the camera, but don't decode it yet
    post_grab_timestamp = time.perf_counter_ns()

    if grab_success:
        triggers.set_frame_grabbed()
    else:
        raise ValueError(f"Failed to grab frame from camera {camera_id}")

    # frame.timestamps.wait_for_retrieve_trigger_timestamp = time.perf_counter_ns()

    triggers.await_retrieve_trigger()

    pre_retrieve_timestamp = time.perf_counter_ns()
    retrieve_success, image = cap.retrieve()  # decode the frame into an image
    post_retrieve_return = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {camera_id}")
    triggers.set_frame_retrieved()

    timestamps_npy = timestamps_to_npy(pre_grab_timestamp=pre_grab_timestamp,
                                       post_grab_timestamp=post_grab_timestamp,
                                       pre_retrieve_timestamp=pre_retrieve_timestamp,
                                       post_retrieve_return=post_retrieve_return,
                                       timestamp_ns=(pre_grab_timestamp + post_grab_timestamp) // 2)
    camera_shared_memory.put_new_frame(
        frame=frame,
        image=image,
    )
    return FramePayload.from_previous(frame)
