import logging
import traceback

import cv2

from fast_camera_capture.opencv.camera.models.webcam_config import WebcamConfig

logger = logging.getLogger(__name__)


def apply_configuration(cv2_vid_cap: cv2.VideoCapture, config: WebcamConfig):
    # set camera stream parameters
    logger.info(
        f"Applying configuration to Camera {config.webcam_id}:"
        f"Exposure: {config.exposure}, "
        f"Resolution width: {config.resolution_width}, "
        f"Resolution height: {config.resolution_height}, "
        f"Fourcc: {config.fourcc}"
    )
    try:
        if not cv2_vid_cap.isOpened():
            logger.error(
                f"Failed to apply configuration to Camera {config.webcam_id} - camera is "
                f"not open"
            )
            return
    except Exception as e:
        logger.error(
            f"Failed when trying to check if Camera {config.webcam_id} is open"
        )
        return

    try:
        cv2_vid_cap.set(
            cv2.CAP_PROP_EXPOSURE, config.exposure
        )
        cv2_vid_cap.set(
            cv2.CAP_PROP_FRAME_WIDTH, config.resolution_width
        )
        cv2_vid_cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT, config.resolution_height
        )

        cv2_vid_cap.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.fourcc)
        )
    except Exception as e:
        logger.error(
            f"Problem applying configuration for camera: {config.webcam_id}"
        )
        traceback.print_exc()
        raise e
