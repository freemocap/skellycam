import logging
import sys

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.determine_backend import determine_opencv_camera_backend
from skellycam.core.camera.opencv.opencv_helpers.opencv_apply_config import apply_camera_configuration
from skellycam.utilities.wait_functions import wait_1s


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


logger = logging.getLogger(__name__)

# Minimum buffer size to reduce stale-frame latency.
# USB cameras deliver frames into an OS driver ring buffer (typically 2-4 frames deep).
# When our grab() loop falls behind, a larger buffer means we dequeue frames that were
# captured tens of milliseconds ago, making our grab timestamps a poor proxy for actual
# capture time. Setting this to 1 ensures grab() always returns the most recent frame
# the driver has available.
# NOTE: Not all backends honor this (MSMF ignores it). DSHOW on Windows does respect it.
_PREFERRED_BUFFER_SIZE = 1


def create_cv2_video_capture(config: CameraConfig, retry_count: int = 5) -> tuple[cv2.VideoCapture, CameraConfig]:
    cap_backend = determine_opencv_camera_backend()
    attempts = -1
    capture: cv2.VideoCapture | None = None
    while attempts < retry_count and capture is None:
        attempts += 1
        capture = cv2.VideoCapture(int(config.camera_index), cap_backend.id)
        if not capture.isOpened():
            if attempts < retry_count:
                logger.warning(
                    f"Failed to open camera {config.camera_index}. Retrying... ({attempts + 1}/{retry_count})")
                capture.release()
                wait_1s()
                capture = None
                continue
            raise FailedToOpenCameraException()

        # Minimize the driver-side frame buffer to reduce stale-frame latency.
        # This makes grab() timestamps a tighter proxy for actual frame capture time.
        if not capture.set(cv2.CAP_PROP_BUFFERSIZE, _PREFERRED_BUFFER_SIZE):
            logger.debug(
                f"Camera {config.camera_index}: backend did not accept "
                f"CAP_PROP_BUFFERSIZE={_PREFERRED_BUFFER_SIZE} (this is normal for some backends)"
            )
        else:
            actual = capture.get(cv2.CAP_PROP_BUFFERSIZE)
            logger.debug(f"Camera {config.camera_index}: buffer size set to {int(actual)}")

        success, image = capture.read()

        if not success or image is None:
            if attempts < retry_count:
                logger.warning(
                    f"Failed to read frame from camera {config.camera_index}. Retrying... ({attempts + 1}/{retry_count})")
                capture.release()
                wait_1s()
                capture = None
                continue
            raise FailedToReadFrameFromCameraException()
    if not isinstance(capture, cv2.VideoCapture) or not capture.isOpened():
        raise FailedToOpenCameraException(f"Failed to open camera {config.camera_index} after {retry_count} attempts.")
    extracted_config = apply_camera_configuration(cv2_vid_capture=capture,
                                                  prior_config=None,
                                                  config=config)
    logger.info(f"Created `cv2.VideoCapture` object for Camera: {config.camera_index}")
    return capture, extracted_config