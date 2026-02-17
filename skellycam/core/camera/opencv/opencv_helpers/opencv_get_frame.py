import logging
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def opencv_get_frame(cap: cv2.VideoCapture,
                     frame_rec_array: np.recarray) -> tuple[bool, np.recarray]:
    """
    THIS IS WHERE THE MAGIC HAPPENS

    This method retrieves the next frame that was captured by the camera sensor.

    The sensor itself runs on its own internal clock — it integrates photons at a fixed interval
    (e.g. every 33.3ms at 30fps) regardless of what our software does. The actual moment of
    transduction — when environmental energy (a timeslice of the 2D pattern of light intensity
    in 3 wavelengths within the camera's field of view) is absorbed by the CMOS sensor and
    converted into electrical charge — happened some milliseconds BEFORE this code runs.

    We cannot observe that moment directly from software. The closest proxy we have is the
    grab() timestamp, which records when the OS video driver delivered the captured frame data
    to our process. The gap between true photon capture and our timestamp includes:
      - Sensor readout time (rolling shutter scans top-to-bottom over ~10-20ms on consumer cameras)
      - USB isochronous transfer latency (~125μs per microframe)
      - OS driver buffering and scheduling jitter (~0.1-1ms)

    We decouple the grab() and retrieve() operations so that all cameras can grab() in tight
    succession before any camera spends time on the heavier retrieve() decode step. This
    minimizes the inter-camera timing spread of the grab timestamps, giving us the best
    possible multi-camera synchronization achievable in software with USB cameras.

    The grab()/retrieve() split works as follows:
      - grab() tells the backend "dequeue the next available frame from the driver buffer."
        On DSHOW this calls IMediaSample delivery; on MSMF it calls ReadSample().
        With buffer_size=1, this gives us the most recently captured frame rather than a
        stale one from the ring buffer.
      - retrieve() decodes the raw frame data (e.g. MJPEG→BGR) into the pixel array.
        This is the expensive step (~0.1-20ms depending on whether the decoder had the
        frame ready or is still processing it).

    The midpoint of (pre_grab, post_grab) is our best available proxy for when this
    particular frame was captured by the sensor — not exact, but the closest we can get
    without direct access to the UVC hardware presentation timestamps.

    This sweet baby must be protected at all costs.

    Ref: https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html#ae38c2a053d39d6b20c9c649e08ff0146
    """

    frame_rec_array.frame_metadata.timestamps.pre_frame_grab_ns[0] = time.perf_counter_ns()
    grab_success = cap.grab()  # Dequeue the most recent captured frame from the driver buffer ✨
    frame_rec_array.frame_metadata.timestamps.post_frame_grab_ns[0] = time.perf_counter_ns()

    if not grab_success:
        logger.error(f"Failed to grab frame from camera{frame_rec_array.frame_metadata.camera_config.camera_id[0]}")
        return False, frame_rec_array

    # Decode the raw frame data (typically MJPEG) into a BGR pixel array.
    #
    # The photons have already been captured — the sensor integrated light during its exposure
    # interval some milliseconds ago, and the camera's internal electronics read out the charge
    # from each photosite, digitized it, and streamed the compressed result over USB.
    #
    # retrieve() unpacks that compressed payload into the dense array of pixel values that all
    # of our downstream computation and inference will be grounded in. This is where the raw
    # measurement becomes a usable digital image.

    frame_rec_array.frame_metadata.timestamps.pre_frame_retrieve_ns[0] = time.perf_counter_ns()
    retrieve_success, _ = cap.retrieve(image=frame_rec_array.image[0])  # provide pre-allocated image for speed
    frame_rec_array.frame_metadata.timestamps.post_frame_retrieve_ns[0] = time.perf_counter_ns()

    if not retrieve_success:
        logger.error(f"Failed to retrieve frame from camera {frame_rec_array.frame_metadata.camera_config.camera_id[0]}")
        return False, frame_rec_array

    frame_rec_array.frame_metadata.frame_number[0] += 1
    return True, frame_rec_array