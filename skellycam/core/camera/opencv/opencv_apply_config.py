import logging

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.extract_config import extract_config_from_cv2_capture
from skellycam.system.diagnostics.recommend_camera_exposure_setting import get_recommended_cv2_cap_exposure, \
    ExposureModes

logger = logging.getLogger(__name__)

AUTO_EXPOSURE_SETTING = 3  # 0.75?
MANUAL_EXPOSURE_SETTING = 1  # 0.25?

class FailedToApplyCameraConfigurationError(Exception):
    pass


def apply_camera_configuration(cv2_vid_capture: cv2.VideoCapture,
                               prior_config: CameraConfig | None,
                               config: CameraConfig) -> CameraConfig:
    # set camera stream parameters

    logger.info(
        f"Applying configuration to Camera {config.camera_index}:\n{config}"
    )
    # Handle exposure mode and settings

    apply_exposure_mode = prior_config is None or prior_config.exposure_mode != config.exposure_mode
    apply_exposure_value = prior_config is None or prior_config.exposure != config.exposure
    apply_resolution = prior_config is None or prior_config.resolution != config.resolution
    apply_framerate = prior_config is None or prior_config.framerate != config.framerate
    apply_capture_fourcc = prior_config is None or prior_config.capture_fourcc != config.capture_fourcc

    try:
        if not cv2_vid_capture.isOpened():
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_index} - Camera is not open"
            )

        if apply_exposure_mode:
            if config.exposure_mode == ExposureModes.RECOMMEND.name:
                optimized_exposure = get_recommended_cv2_cap_exposure(cv2_vid_capture)
                cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING)
                cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(optimized_exposure))
                logger.info(f"Setting camera {config.camera_index} to recommended exposure: {optimized_exposure}")
            elif config.exposure_mode == ExposureModes.AUTO.name:
                cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_SETTING)
            elif config.exposure_mode == ExposureModes.MANUAL.name:
                cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING)
                cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))
        elif config.exposure_mode == ExposureModes.MANUAL.name and apply_exposure_value:
            # Only update exposure value if in manual mode and the value changed
            cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))

        # Handle resolution changes
        if apply_resolution:
            cv2_vid_capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
            cv2_vid_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)


        if apply_framerate:
            cv2_vid_capture.set(cv2.CAP_PROP_FPS, config.framerate)


        if apply_capture_fourcc:
            cv2_vid_capture.set(
                cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.capture_fourcc)
            )
        extracted_config = extract_config_from_cv2_capture(camera_index=config.camera_index,
                                                              camera_id=config.camera_id,
                                                           camera_name=config.camera_name,
                                                           cv2_capture=cv2_vid_capture,
                                                           exposure_mode=ExposureModes.MANUAL.name if config.exposure_mode == ExposureModes.RECOMMEND.name else config.exposure_mode,  # set to manual after running recommended routine
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
