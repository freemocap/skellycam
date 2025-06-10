import logging

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.determine_backend import determine_backend
from skellycam.core.camera.opencv.opencv_apply_config import apply_camera_configuration
from skellycam.utilities.wait_functions import wait_1s


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


logger = logging.getLogger(__name__)


def create_cv2_video_capture(config: CameraConfig, retry_count: int = 5) -> tuple[cv2.VideoCapture, CameraConfig]:
    cap_backend = determine_backend()
    attempts = -1
    capture: cv2.VideoCapture| None = None
    while attempts < retry_count and capture is None:
        attempts += 1
        capture = cv2.VideoCapture(int(config.camera_index), cap_backend.value)
        if not capture.isOpened():
            if attempts < retry_count:
                logger.warning(f"Failed to open camera {config.camera_index}. Retrying... ({attempts + 1}/{retry_count})")
                capture.release()
                wait_1s()
                capture =None
                continue
            raise FailedToOpenCameraException()
        success, image = capture.read()

        if not success or image is None:
            if attempts < retry_count:
                logger.warning(f"Failed to read frame from camera {config.camera_index}. Retrying... ({attempts + 1}/{retry_count})")
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
