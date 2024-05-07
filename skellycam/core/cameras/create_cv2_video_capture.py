import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.determine_backend import determine_backend


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


import logging

logger = logging.getLogger(__name__)


def create_cv2_capture(config: CameraConfig):
    cap_backend = determine_backend()
    capture = cv2.VideoCapture(int(config.camera_id), cap_backend.value)
    if not capture.isOpened():
        raise FailedToOpenCameraException()
    success, image = capture.read()

    if not success or image is None:
        raise FailedToReadFrameFromCameraException()

    logger.debug(f"Created `cv2.VideoCapture` object for Camera: {config.camera_id}")
    return capture
