import os

import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.opencv.determine_backend import determine_backend


# from skellycam.tests.mocks import create_cv2_video_capture_mock


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


import logging

logger = logging.getLogger(__name__)


def create_cv2_capture(config: CameraConfig):

    if os.getenv("TEST_ENV") == "true":
        # TODO - find a way to get this 'test' stuff out of the working code (but for the moment i think its worth the slop)
        logger.debug(f"Running in test environment, using mock camera")
        # return create_cv2_video_capture_mock(config)
        raise NotImplementedError("Mocking is not yet implemented")

    cap_backend = determine_backend()
    capture = cv2.VideoCapture(int(config.camera_id), cap_backend.value)
    if not capture.isOpened():
        raise FailedToOpenCameraException()
    success, image = capture.read()

    if not success or image is None:
        raise FailedToReadFrameFromCameraException()

    logger.info(f"Created `cv2.VideoCapture` object for Camera: {config.camera_id}")
    return capture
