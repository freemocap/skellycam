import logging
import traceback

import cv2

from skellycam.backend.core.cameras.config.camera_config import CameraConfig
from skellycam.backend.core.cameras.config.extract_config import extract_config_from_cv2_capture

logger = logging.getLogger(__name__)


class FailedToApplyCameraConfigurationError(Exception):
    pass


def apply_camera_configuration(cv2_vid_capture: cv2.VideoCapture, config: CameraConfig,
                               strict: bool = False) -> CameraConfig:
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
        if not cv2_vid_capture.isOpened():
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_id} - Camera is not open"
            )
        cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))
        cv2_vid_capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
        cv2_vid_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)
        cv2_vid_capture.set(cv2.CAP_PROP_FPS, config.framerate)
        cv2_vid_capture.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.capture_fourcc)
        )
        extracted_config = extract_config_from_cv2_capture(cv2_capture=cv2_vid_capture,
                                                           rotation=config.rotation,
                                                           use_this_camera=config.use_this_camera)

        if strict:
            if extracted_config != config:
                logger.error(
                    f"Failed to apply configuration to Camera {config.camera_id} - "
                    f"Configuration mismatch: {config} != {extracted_config}"
                )
                raise FailedToApplyCameraConfigurationError(
                    f"Failed to apply configuration to Camera {config.camera_id} - Configuration mismatch"
                )

        return extracted_config
    except Exception as e:
        logger.error(f"Problem applying configuration for camera: {config.camera_id}")
        traceback.print_exc()
        raise FailedToApplyCameraConfigurationError(
            f"Failed to apply configuration to Camera {config.camera_id} - {type(e).__name__} - {e}"
        )
