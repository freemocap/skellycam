import logging

import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core import CameraId
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.detection.image_rotation_types import RotationTypes

logger = logging.getLogger(__name__)


def extract_config_from_cv2_capture(camera_id: CameraId,
        cv2_capture: cv2.VideoCapture,
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
            exposure=cv2_capture.get(cv2.CAP_PROP_EXPOSURE),
            framerate=cv2_capture.get(cv2.CAP_PROP_FPS),
            rotation=rotation,
        )
    except Exception as e:
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - {type(e).__name__}: {e}")