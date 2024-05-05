import cv2

from skellycam.backend.core.cameras.config.camera_config import CameraConfig
from skellycam.backend.core.cameras.config.determine_backend import determine_backend


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


import logging

logger = logging.getLogger(__name__)


async def create_cv2_capture(config: CameraConfig):
    cap_backend = determine_backend()
    logger.info(
        f"Creating cv.VideoCapture object for Camera: {config.camera_id} using backend `{cap_backend.name}`..."
    )

    capture = cv2.VideoCapture(int(config.camera_id), cap_backend.value)
    if not capture.isOpened():
        raise FailedToOpenCameraException()
    success, image = capture.read()

    if not success or image is None:
        raise FailedToReadFrameFromCameraException()

    logger.info(f"Successfully connected to Camera: {config.camera_id}!")
    return capture
