import traceback

import cv2

from skellycam.system.environment.get_logger import logger
from skellycam.models.cameras.camera_config import CameraConfig


class FailedToApplyCameraConfigurationError(Exception):
    pass


def apply_camera_configuration(cv2_vid_cap: cv2.VideoCapture, config: CameraConfig):
    # set camera stream parameters
    logger.info(
        f"Applying configuration to Camera {config.camera_id}:"
        f"Exposure: {config.exposure}, "
        f"Resolution width: {config.resolution.width}, "
        f"Resolution height: {config.resolution.height}, "
        f"Framerate: {config.framerate}, "
        f"Fourcc: {config.capture_fourcc}"
    )
    try:
        if not cv2_vid_cap.isOpened():
            logger.error(
                f"Failed to apply configuration to Camera {config.camera_id} - camera is "
                f"not open"
            )
            return
    except Exception as e:
        logger.error(
            f"Failed when trying to check if Camera {config.camera_id} is open"
        )
        return

    try:
        cv2_vid_cap.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))
        cv2_vid_cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
        cv2_vid_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)
        cv2_vid_cap.set(cv2.CAP_PROP_FPS, config.framerate)
        cv2_vid_cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.capture_fourcc))
    except Exception as e:
        logger.error(f"Problem applying configuration for camera: {config.camera_id}")
        traceback.print_exc()
        raise e

    if not cv2_vid_cap.isOpened():
        logger.error(
            f"Failed to apply configuration to Camera {config.camera_id} - camera is "
            f"not open"
        )
        raise FailedToApplyCameraConfigurationError(
            f"Failed to apply configuration to Camera {config.camera_id} - camera is "
            f"not open"
        )