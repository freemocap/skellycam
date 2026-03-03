import logging
import sys

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.opencv_extract_config import extract_config_from_cv2_capture
from skellycam.system.diagnostics.recommend_camera_exposure_setting import get_recommended_cv2_cap_exposure, \
    ExposureModes

logger = logging.getLogger(__name__)

AUTO_EXPOSURE_SETTING = 3
MANUAL_EXPOSURE_SETTING = 1


class FailedToApplyCameraConfigurationError(Exception):
    pass


def _apply_exposure(cv2_vid_capture: cv2.VideoCapture, config: CameraConfig) -> None:
    """Apply exposure settings to the capture device.

    On Linux/V4L2 the exposure unit convention differs from Windows/DSHOW (absolute
    device units vs log2-seconds), and the values coming from the frontend are
    calibrated for Windows.  Until we have proper cross-platform exposure calibration,
    force auto-exposure on Linux so the camera produces usable frames.
    """
    if sys.platform == "linux":
        logger.info(
            f"Camera {config.camera_index}: forcing auto-exposure on Linux "
            f"(requested mode={config.exposure_mode}, value={config.exposure})"
        )
        cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_SETTING)
        return

    if config.exposure_mode == ExposureModes.RECOMMEND.name:
        optimized = get_recommended_cv2_cap_exposure(cv2_vid_capture)
        cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING)
        cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(optimized))
        config.exposure = optimized
        config.exposure_mode = ExposureModes.MANUAL.name
    elif config.exposure_mode == ExposureModes.AUTO.name:
        cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_SETTING)
    elif config.exposure_mode == ExposureModes.MANUAL.name:
        cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING)
        cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))


def apply_camera_configuration(cv2_vid_capture: cv2.VideoCapture,
                               prior_config: CameraConfig | None,
                               config: CameraConfig) -> CameraConfig:
    initial_config = prior_config is None

    if initial_config:
        logger.info(f"Applying initial configuration to Camera {config.camera_index}:\n{config}")
    else:
        logger.info(f"Applying configuration to Camera {config.camera_index}:\n{config}")

    should_apply_exposure = initial_config or prior_config.exposure_mode != config.exposure_mode or prior_config.exposure != config.exposure
    should_apply_resolution = initial_config or prior_config.resolution != config.resolution
    should_apply_framerate = False  # framerate application is disabled
    should_apply_capture_fourcc = initial_config or prior_config.capture_fourcc != config.capture_fourcc

    try:
        if not cv2_vid_capture.isOpened():
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_index} - Camera is not open"
            )

        if should_apply_exposure:
            _apply_exposure(cv2_vid_capture, config)

        if should_apply_resolution:
            cv2_vid_capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
            cv2_vid_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)

        if should_apply_framerate:
            if config.framerate > 0:
                cv2_vid_capture.set(cv2.CAP_PROP_FPS, config.framerate)

        if should_apply_capture_fourcc:
            cv2_vid_capture.set(
                cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.capture_fourcc)
            )

        extracted_config = extract_config_from_cv2_capture(cv2_capture=cv2_vid_capture,
                                                           camera_index=config.camera_index,
                                                           camera_id=config.camera_id,
                                                           camera_name=config.camera_name,
                                                           exposure_mode=config.exposure_mode,
                                                           rotation=config.rotation)
        if not cv2_vid_capture.isOpened() or extracted_config is None:
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_index} - Camera closed when applying configuration"
            )
        logger.trace(f"Camera {config.camera_index} configuration applied, extracted config: {extracted_config}")
        return extracted_config
    except Exception as e:
        logger.exception(f"Problem applying configuration for camera: {config},\n\nReceived error:    {e}")
        raise FailedToApplyCameraConfigurationError(
            f"Failed to apply configuration to Camera {config.camera_index} - {type(e).__name__} - {e}"
        )