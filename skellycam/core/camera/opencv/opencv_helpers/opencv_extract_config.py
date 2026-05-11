import logging
from sys import platform

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera.config.image_rotation_types import RotationTypes
from skellycam.core.types.type_overloads import CameraIndexInt
from skellycam.core.camera.opencv.opencv_helpers.recommend_camera_exposure_setting import ExposureModes

logger = logging.getLogger(__name__)


def decode_fourcc(fourcc_value: float) -> str:
    fourcc_int = int(fourcc_value)
    return "".join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4))


def extract_config_from_cv2_capture(camera_index: CameraIndexInt,
                                    camera_id: str,
                                    camera_name: str,
                                    cv2_capture: cv2.VideoCapture,
                                    exposure_mode: str = ExposureModes.MANUAL.name,
                                    rotation: RotationTypes = RotationTypes.NO_ROTATION, ) -> CameraConfig:
    width = int(cv2_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cv2_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    exposure = int(cv2_capture.get(cv2.CAP_PROP_EXPOSURE))
    framerate = cv2_capture.get(cv2.CAP_PROP_FPS)
    fourcc_raw = cv2_capture.get(cv2.CAP_PROP_FOURCC)
    fourcc_string = decode_fourcc(fourcc_raw)
    logger.trace(f"\n\n\n Camera {camera_index} - Extracted config from cv2.VideoCapture: "
                 f"\n- int(cv2_capture.get(cv2.CAP_PROP_FRAME_WIDTH))={width}, "
                 f"\n- int(cv2_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))={height}, "
                 f"\n- int(cv2_capture.get(cv2.CAP_PROP_EXPOSURE))={exposure}, "
                 f"\n- cv2_capture.get(cv2.CAP_PROP_FPS)={framerate}, "
                 f"\n- decode_fourcc(cv2_capture.get(cv2.CAP_PROP_FOURCC))={fourcc_string}\n\n\n")

    if any([
        width == 0, 
        height == 0, 
        not (platform == "darwin") and exposure == 0  # macOS always returns 0 for exposure
    ]):
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - "
                     f"width: {width}, height: {height}, exposure: {exposure}")
        raise ValueError("Invalid camera configuration detected. Please check the camera settings.")
    try:
        return CameraConfig(
            camera_index=camera_index,
            camera_id=camera_id,
            camera_name=camera_name,
            resolution=ImageResolution(
                width=width,
                height=height
            ),
            exposure_mode=exposure_mode,
            exposure=exposure,
            framerate=framerate,
            rotation=rotation,
            capture_fourcc=fourcc_string,
        )
    except Exception as e:
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - {type(e).__name__}: {e}")
        raise
