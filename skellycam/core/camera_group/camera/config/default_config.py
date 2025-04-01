from enum import Enum

from skellycam.core import CameraIndex
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes
from skellycam.system.diagnostics.recommend_camera_exposure_setting import ExposureModes

# DEFAULT_EXPOSURE = -7

DEFAULT_IMAGE_HEIGHT: int = 720
DEFAULT_IMAGE_WIDTH: int = 1280
DEFAULT_IMAGE_CHANNELS: int = 3
DEFAULT_FRAME_RATE: float = 30.0
DEFAULT_IMAGE_SHAPE: tuple = (DEFAULT_IMAGE_HEIGHT, DEFAULT_IMAGE_WIDTH, DEFAULT_IMAGE_CHANNELS)
DEFAULT_CAMERA_INDEX: CameraIndex = CameraIndex(0)
DEFAULT_CAMERA_NAME: str = "Default Camera"
DEFAULT_RESOLUTION: ImageResolution = ImageResolution(height=DEFAULT_IMAGE_HEIGHT, width=DEFAULT_IMAGE_WIDTH)


class DefaultCameraConfig(Enum):
    CAMERA_NAME = DEFAULT_CAMERA_NAME
    CAMERA_INDEX = DEFAULT_CAMERA_INDEX
    USE_THIS_CAMERA = True
    RESOLUTION = DEFAULT_RESOLUTION
    COLOR_CHANNELS: int = DEFAULT_IMAGE_CHANNELS
    EXPOSURE_MODE: str = ExposureModes.MANUAL.name
    EXPOSURE: int = -7
    FRAMERATE: float = DEFAULT_FRAME_RATE
    ROTATION: RotationTypes = RotationTypes.NO_ROTATION
    CAPTURE_FOURCC: str = "MJPG"  # skellycam/system/diagnostics/run_cv2_video_capture_diagnostics.py
    WRITER_FOURCC: str = "X264"  # Need set up our installer and whanot so we can us `X264` (or H264, if its easier to set up) skellycam/system/diagnostics/run_cv2_video_writer_diagnostics.py
