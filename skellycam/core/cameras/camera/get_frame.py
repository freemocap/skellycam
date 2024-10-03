import logging
import multiprocessing
import time

import cv2

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_triggers import CameraTriggers
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    create_empty_frame_metadata
from skellycam.core.shmemory.camera_shared_memory import CameraSharedMemory

logger = logging.getLogger(__name__)


def get_frame(camera_id: CameraId,
              cap: cv2.VideoCapture,
              camera_shared_memory: CameraSharedMemory,
              triggers: CameraTriggers,
              frame_number: int,
              ) -> int:
    """
    THIS IS WHERE THE MAGIC HAPPENS

    This method is responsible for grabbing the next frame from the camera - it is the point of "transduction"
     when a pattern of environmental energy (i.e. a timeslice of the 2D pattern of light intensity in 3 wavelengths
      within the field of view of the camera ) is absorbed by the camera's sensor and converted into a digital
      representation of that pattern (i.e. a 2D array of pixel values in 3 channels).

    This is the empirical measurement, whereupon all future inference will derive their epistemological grounding.

    This sweet baby must be protected at all costs.

    ===

    We use external triggers and decouple frame `grab` and `retrieve` operations to ensure that we can
    get as tight of a synchronization as possible between the cameras
    # https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146
    """
    logger.loop(f"Frame#{frame_number} - Camera {camera_id} awaiting `grab` trigger...")
    frame_metadata = create_empty_frame_metadata(camera_id=camera_id, frame_number=frame_number)
    triggers.await_grab_trigger()

    frame_metadata[FRAME_METADATA_MODEL.PRE_GRAB_TIMESTAMP_NS.value] = time.perf_counter_ns()
    grab_success = cap.grab()  # grab the frame from the camera, but don't decode it yet
    frame_metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value] = time.perf_counter_ns()

    if grab_success:
        triggers.set_frame_grabbed()
    else:
        raise ValueError(f"Failed to grab frame from camera {camera_id}")

    triggers.await_retrieve_trigger()

    frame_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()
    # decode the frame buffer into an image! Wow, magic!
    retrieve_success, image = cap.retrieve()  # This is how the light gets in ✨
    frame_metadata[FRAME_METADATA_MODEL.POST_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {camera_id}")

    triggers.set_frame_retrieved()

    camera_shared_memory.put_new_frame(
        image=image,
        metadata=frame_metadata,
    )
    triggers.set_new_frame_available()
    return frame_number + 1
