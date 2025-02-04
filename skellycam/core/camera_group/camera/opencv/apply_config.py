import logging
import traceback

import cv2

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera.config.extract_config import extract_config_from_cv2_capture
from skellycam.system.diagnostics.recommend_camera_exposure_setting import get_recommended_cv2_cap_exposure, \
    ExposureModes

logger = logging.getLogger(__name__)

AUTO_EXPOSURE_SETTING = 3  # 0.75?
MANUAL_EXPOSURE_SETTING = 1  # 0.25?

class FailedToApplyCameraConfigurationError(Exception):
    pass


def apply_camera_configuration(cv2_vid_capture: cv2.VideoCapture, config: CameraConfig, initial: bool = False) -> CameraConfig:
    # set camera stream parameters

    logger.info(
        f"Applying configuration to Camera {config.camera_id}:\n"
        f"\tExposure Mode: {config.exposure_mode},\n"
        f"\tExposure: {config.exposure if config.exposure_mode == ExposureModes.MANUAL else 'N/A'},\n"
        f"\tResolution height: {config.resolution.height},\n"
        f"\tResolution width: {config.resolution.width},\n"
        f"\tFramerate: {config.framerate},\n"
        f"\tFourcc: {config.capture_fourcc}"
    )
    try:
        if not cv2_vid_capture.isOpened():
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_id} - Camera is not open"
            )
        if config.exposure_mode == ExposureModes.RECOMMENDED.name or initial:
            optimized_exposure = get_recommended_cv2_cap_exposure(cv2_vid_capture)
            cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING)
            cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(optimized_exposure))
            logger.info(f"Setting camera {config.camera_id} to recommended exposure: {optimized_exposure}")
        elif config.exposure_mode == ExposureModes.AUTO.name:
            cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_SETTING)
        elif config.exposure_mode == ExposureModes.MANUAL.name:
            cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING)
            cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))

        cv2_vid_capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
        cv2_vid_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)
        cv2_vid_capture.set(cv2.CAP_PROP_FPS, config.framerate)
        cv2_vid_capture.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.capture_fourcc)
        )
        extracted_config = extract_config_from_cv2_capture(camera_id=config.camera_id,
                                                           cv2_capture=cv2_vid_capture,
                                                           exposure_mode=ExposureModes.MANUAL.name, # set to manual after running recommended routine the first time
                                                           rotation=config.rotation,
                                                           use_this_camera=config.use_this_camera)
        if not cv2_vid_capture.isOpened() or extracted_config is None:
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_id} - Camera closed when applying configuration"
            )
        logger.trace(f"Camera {config.camera_id} configuration applied, extracted config: {extracted_config}")
        return extracted_config
    except Exception as e:
        logger.error(f"Problem applying configuration for camera: {config.camera_id}")
        traceback.print_exc()
        raise FailedToApplyCameraConfigurationError(
            f"Failed to apply configuration to Camera {config.camera_id} - {type(e).__name__} - {e}"
        )
