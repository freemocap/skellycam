import logging
import traceback

import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.extract_config import extract_config_from_cv2_capture

logger = logging.getLogger(__name__)


class FailedToApplyCameraConfigurationError(Exception):
    pass


def apply_camera_configuration(
    cv2_vid_capture: cv2.VideoCapture, config: CameraConfig
) -> CameraConfig:
    # set camera stream parameters

    logger.info(
        f"Applying configuration to Camera {config.camera_id}:\n"
        f"\tExposure: {config.exposure},\n"
        f"\tResolution height: {config.resolution.height},\n"
        f"\tResolution width: {config.resolution.width},\n"
        f"\tFramerate: {config.frame_rate},\n"
        f"\tFourcc: {config.capture_fourcc}"
    )
    try:
        if not cv2_vid_capture.isOpened():
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_id} - Camera is not open"
            )
        cv2_vid_capture.set(cv2.CAP_PROP_EXPOSURE, float(config.exposure))
        cv2_vid_capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
        cv2_vid_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)
        cv2_vid_capture.set(cv2.CAP_PROP_FPS, config.frame_rate)
        cv2_vid_capture.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*config.capture_fourcc)
        )
        extracted_config = extract_config_from_cv2_capture(
            camera_id=config.camera_id,
            cv2_capture=cv2_vid_capture,
            rotation=config.rotation,
            use_this_camera=config.use_this_camera,
        )

        verify_applied_config(provided_config=config, extracted_config=extracted_config)  #TODO: we might not want to error out here, although a mismatch in configs could cause problems elsewhere

        return extracted_config
    except Exception as e:
        logger.error(f"Problem applying configuration for camera: {config.camera_id}")
        traceback.print_exc()
        raise FailedToApplyCameraConfigurationError(
            f"Failed to apply configuration to Camera {config.camera_id} - {type(e).__name__} - {e}"
        )


def verify_applied_config(
    provided_config: CameraConfig, extracted_config: CameraConfig
) -> None:
    # TODO: the __eq__ method in Camera Config achieves this, but without good reporting on where they aren't equal
    assert (
        extracted_config.camera_id == provided_config.camera_id
    ), f"Provided camera id {provided_config.camera_id} does not match extracted camera id {extracted_config.camera_id}"
    assert (
        extracted_config.exposure == provided_config.exposure
    ), f"Provided camera exposure {provided_config.exposure} does not match extracted camera exposure {extracted_config.exposure}"
    assert (
        extracted_config.resolution.height == provided_config.resolution.height
    ), f"Provided height {provided_config.resolution.height} does not match extracted height {extracted_config.resolution.height}"
    assert (
        extracted_config.resolution.width == provided_config.resolution.width
    ), f"Provided width {provided_config.resolution.width} does not match extracted width {extracted_config.resolution.width}"
    assert (
        extracted_config.frame_rate == provided_config.frame_rate
    ), f"Provided framerate {provided_config.frame_rate} does not match extracted framerate {extracted_config.frame_rate}"
    assert (
        extracted_config.capture_fourcc == provided_config.capture_fourcc
    ), f"Provided fourcc {provided_config.capture_fourcc} does not match extracted fourcc {extracted_config.capture_fourcc}"
