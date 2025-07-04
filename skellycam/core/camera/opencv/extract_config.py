import logging

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.types.image_rotation_types import RotationTypes
from skellycam.core.types.type_overloads import CameraIndexInt
from skellycam.system.diagnostics.recommend_camera_exposure_setting import ExposureModes

logger = logging.getLogger(__name__)


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

    if any([width == 0, height == 0, exposure == 0, framerate == 0]):
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - "
                     f"width: {width}, height: {height}, exposure: {exposure}, framerate: {framerate}")
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
        )
    except Exception as e:
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - {type(e).__name__}: {e}")
        raise
