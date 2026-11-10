import logging
import sys

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig, frame_rates_equal
from skellycam.core.camera.opencv.opencv_helpers.opencv_extract_config import extract_config_from_cv2_capture
from skellycam.core.camera.config.exposure_modes import ExposureModes

logger = logging.getLogger(__name__)

AUTO_EXPOSURE_SETTING = 3
MANUAL_EXPOSURE_SETTING = 1


class FailedToApplyCameraConfigurationError(Exception):
    pass


def frame_rate_changed(current: float, requested: float) -> bool:
    """Whether a request names a frame rate other than the one the camera reports.

    Reported rates are quantized: DirectShow reports 1e7 divided by its integer frame interval in
    100 ns units (30 fps reads back as 30.00003), and 0 when no rate was requested
    [@opencv412DirectShowFrameRate]. Clients send the reported value back, so a relative difference
    below 1e-4 (that quantization, up to 1000 fps) is the same rate. A non-positive request names no
    rate, as when a camera opens.
    """
    return requested > 0 and not frame_rates_equal(requested, current)


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

    # DirectShow uses a boolean here, not V4L2's exposure-mode enum.
    # OpenCV 4.12.0 enables auto only when cvRound(value) == 1.
    # [@opencv412DirectShowControls]
    directshow = int(cv2_vid_capture.get(cv2.CAP_PROP_BACKEND)) == cv2.CAP_DSHOW
    auto_setting = 1.0 if directshow else AUTO_EXPOSURE_SETTING
    manual_setting = 0.0 if directshow else MANUAL_EXPOSURE_SETTING
    if config.exposure_mode == ExposureModes.RECOMMEND.name:
        raise ValueError("Resolve RECOMMEND through CameraBackendManager before applying device settings")
    elif config.exposure_mode == ExposureModes.AUTO.name:
        cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_setting)
    elif config.exposure_mode == ExposureModes.MANUAL.name:
        cv2_vid_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, manual_setting)
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
    # create_cv2_video_capture sets the initial frame rate.
    should_apply_framerate = not initial_config and frame_rate_changed(prior_config.framerate, config.framerate)
    should_apply_capture_fourcc = initial_config or prior_config.capture_fourcc != config.capture_fourcc
    if int(cv2_vid_capture.get(cv2.CAP_PROP_BACKEND)) == cv2.CAP_DSHOW:
        # create_cv2_video_capture already set the initial format in DirectShow's order; setting size and
        # FourCC again would restart the stream twice more, once in YUY2. A size or frame-rate change
        # restarts the stream in the first supported subtype, so FourCC must follow it.
        # [@opencv412DirectShowSetup]
        should_apply_resolution = should_apply_resolution and not initial_config
        should_apply_capture_fourcc = (should_apply_capture_fourcc or should_apply_resolution
                                       or should_apply_framerate) and not initial_config

    try:
        if not cv2_vid_capture.isOpened():
            raise FailedToApplyCameraConfigurationError(
                f"Failed to apply configuration to Camera {config.camera_index} - Camera is not open"
            )

        if should_apply_resolution:
            cv2_vid_capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
            cv2_vid_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)

        if should_apply_framerate:
            cv2_vid_capture.set(cv2.CAP_PROP_FPS, config.framerate)

        if should_apply_capture_fourcc:
            cv2_vid_capture.set(
                cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*config.capture_fourcc)
            )

        # Resolution, frame-rate and FourCC changes can reopen the DirectShow stream. Apply
        # exposure to the resulting stream, including an otherwise unchanged
        # exposure value after a format change. [@opencv412DirectShowControls]
        if should_apply_exposure or should_apply_resolution or should_apply_framerate or should_apply_capture_fourcc:
            _apply_exposure(cv2_vid_capture, config)

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
        ) from e
