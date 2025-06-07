import logging
import time

import cv2
import numpy as np

from skellycam.core.frame_payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIndex

logger = logging.getLogger(__name__)


def opencv_get_frame(cap: cv2.VideoCapture,
                     frame_metadata: np.ndarray,
                     camera_shared_memory: FramePayloadSharedMemoryRingBuffer):
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

    camera_index: CameraIndex = frame_metadata[FRAME_METADATA_MODEL.CAMERA_INDEX.value]

    frame_metadata[FRAME_METADATA_MODEL.PRE_GRAB_TIMESTAMP_NS.value] = time.perf_counter_ns()
    grab_success = cap.grab()  # This is as close as we get to the moment of transduction, where the light is captured by the sensor. This is where the light gets in ✨
    frame_metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value] = time.perf_counter_ns()

    if not grab_success:
        raise RuntimeError(f"Failed to grab frame from camera {camera_index}")

    frame_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()
    # TODO - we might be able to give the `retreive` method a shared memory `cv2.Mat` object to write the frame into, which would avoid a copy operation.
    retrieve_success, image = cap.retrieve()  # decode the frame buffer into an image! The light is now in the camera's memory, and we have a digital representation of the pattern of light that was in the field of view of the camera during the last frame/timeslice.
    frame_metadata[FRAME_METADATA_MODEL.POST_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()

    if not retrieve_success:
        raise ValueError(f"Failed to retrieve frame from camera {camera_index}")

    camera_shared_memory.put_frame(
        image=image,
        metadata=frame_metadata,
        overwrite=True
    )
