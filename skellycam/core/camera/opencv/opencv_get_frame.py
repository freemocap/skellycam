import logging
import time

import cv2
import numpy as np

from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBuffer

logger = logging.getLogger(__name__)


def opencv_get_frame(cap: cv2.VideoCapture,
                     frame_rec_array: np.recarray ) -> np.recarray:
    """
    THIS IS WHERE THE MAGIC HAPPENS

    This method is responsible for grabbing the next frame from the camera - it is the point of "transduction"
     when a pattern of environmental energy (i.e. a timeslice of the 2D pattern of light intensity in 3 wavelengths
      within the field of view of the camera ) is absorbed by the camera's sensor and converted into a digital
      representation of that pattern (i.e. a 2D array of pixel values in 3 channels).

    This is the empirical measurement, whereupon all future inference will derive their epistemological grounding.

    This sweet baby must be protected at all costs.

    ===

    We use external frame_loop_flags and decouple frame `grab` and `retrieve` operations to ensure that we can
    get as tight of a synchronization as possible between the cameras
    # https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146
    """

    frame_rec_array.frame_metadata.timestamps.pre_frame_grab_ns[0] = time.perf_counter_ns()
    grab_success = cap.grab()  # This is as close as we get to the moment of transduction, where the light is captured by the sensor. This is where the light gets in ✨
    frame_rec_array.frame_metadata.timestamps.post_frame_grab_ns[0] = time.perf_counter_ns()

    if not grab_success:
        raise RuntimeError(f"Failed to grab frame from camera {frame_rec_array.frame_metadata.camera_config.camera_id[0]}")

    frame_rec_array.frame_metadata.timestamps.pre_frame_retrieve_ns[0] = time.perf_counter_ns()
    # decode the frame buffer into an image!
    # The light is now in the camera's memory,
    # and we have a digital representation of the pattern of light
    # that was in the field of view of the camera during the frame/timeslice
    # when the image was 'grabbed' in the previous step.
    # This is the empirical measurement upon which most/all our future calculations and inferences will be based.
    retrieve_success, _ = cap.retrieve(image=frame_rec_array.image[0])  # provide pre-allocated image for speed
    frame_rec_array.frame_metadata.timestamps.post_frame_retrieve_ns[0] = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {frame_rec_array.frame_metadata.camera_config.camera_id[0]}")
    frame_rec_array.frame_metadata.frame_number[0] += 1
    logger.loop(f"Camera {frame_rec_array.frame_metadata.camera_config.camera_id[0]} grabbed frame {frame_rec_array.frame_metadata.frame_number[0]}")
    return frame_rec_array
