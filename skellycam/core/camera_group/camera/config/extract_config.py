import logging

import cv2

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes
from skellycam.system.diagnostics.recommend_camera_exposure_setting import ExposureModes

logger = logging.getLogger(__name__)


def extract_config_from_cv2_capture(camera_id: CameraId,
                                    cv2_capture: cv2.VideoCapture,
                                    exposure_mode: str = ExposureModes.RECOMMENDED.name,
                                    rotation: RotationTypes = RotationTypes.NO_ROTATION,
                                    use_this_camera: bool = True) -> CameraConfig:
    try:
        return CameraConfig(
            camera_id=camera_id,
            use_this_camera=use_this_camera,
            resolution=ImageResolution(
                width=cv2_capture.get(cv2.CAP_PROP_FRAME_WIDTH),
                height=cv2_capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            ),
            exposure_mode=exposure_mode,
            exposure=cv2_capture.get(cv2.CAP_PROP_EXPOSURE),
            framerate=cv2_capture.get(cv2.CAP_PROP_FPS),
            rotation=rotation,
        )
    except Exception as e:
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - {type(e).__name__}: {e}")
