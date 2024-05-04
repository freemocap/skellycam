import logging

import cv2

from skellycam.backend.core.cameras.config.camera_config import CameraConfig
from skellycam.backend.core.device_detection.image_rotation_types import RotationTypes
from skellycam.backend.core.device_detection.video_resolution import VideoResolution

logger = logging.getLogger(__name__)


def extract_config_from_cv2_capture(cv2_capture: cv2.VideoCapture,
                                    rotation: RotationTypes = RotationTypes.NO_ROTATION,
                                    use_this_camera: bool = True) -> CameraConfig:
    try:
        return CameraConfig(
            camera_id=cv2_capture.get(cv2.CAP_PROP_POS_MSEC),
            use_this_camera=use_this_camera,
            resolution=VideoResolution(
                width=cv2_capture.get(cv2.CAP_PROP_FRAME_WIDTH),
                height=cv2_capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            ),
            exposure=cv2_capture.get(cv2.CAP_PROP_EXPOSURE),
            framerate=cv2_capture.get(cv2.CAP_PROP_FPS),
            rotation=rotation,
            capture_fourcc=cv2_capture.get(cv2.CAP_PROP_FOURCC),
            writer_fourcc=cv2_capture.get(cv2.CAP_PROP_FOURCC),
        )
    except Exception as e:
        logger.error(f"Failed to extract configuration from cv2.VideoCapture object - {type(e).__name__}: {e}")
