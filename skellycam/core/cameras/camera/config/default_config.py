from enum import Enum

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.image_resolution import ImageResolution
from skellycam.core.cameras.camera.config.image_rotation_types import RotationTypes

DEFAULT_EXPOSURE = -7

DEFAULT_IMAGE_HEIGHT: int = 720
DEFAULT_IMAGE_WIDTH: int = 1280
DEFAULT_IMAGE_CHANNELS: int = 3
DEFAULT_FRAME_RATE: float = 30.0
DEFAULT_IMAGE_SHAPE: tuple = (DEFAULT_IMAGE_HEIGHT, DEFAULT_IMAGE_WIDTH, DEFAULT_IMAGE_CHANNELS)
DEFAULT_CAMERA_ID: CameraId = CameraId(0)
DEFAULT_RESOLUTION: ImageResolution = ImageResolution(height=DEFAULT_IMAGE_HEIGHT, width=DEFAULT_IMAGE_WIDTH)


class DefaultCameraConfig(Enum):
    CAMERA_ID = DEFAULT_CAMERA_ID
    USE_THIS_CAMERA = True
    RESOLUTION = DEFAULT_RESOLUTION
    COLOR_CHANNELS: int = DEFAULT_IMAGE_CHANNELS
    EXPOSURE: int = DEFAULT_EXPOSURE
    FRAMERATE: float = DEFAULT_FRAME_RATE
    ROTATION: RotationTypes = RotationTypes.NO_ROTATION
    CAPTURE_FOURCC: str = "MJPG"  # skellycam/system/diagnostics/run_cv2_video_capture_diagnostics.py
    WRITER_FOURCC: str = "MP4V"  # Need set up our installer and whanot so we can us `X264` (or H264, if its easier to set up) skellycam/system/diagnostics/run_cv2_video_writer_diagnostics.py
