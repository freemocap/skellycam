from enum import Enum

from skellycam.core import CameraId
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.detection.image_rotation_types import RotationTypes

DEFAULT_IMAGE_HEIGHT: int = 1080
DEFAULT_IMAGE_WIDTH: int = 1920
DEFAULT_CAMERA_ID: CameraId = CameraId(0)
DEFAULT_RESOLUTION: ImageResolution = ImageResolution(height=DEFAULT_IMAGE_HEIGHT, width=DEFAULT_IMAGE_WIDTH)


class DefaultCameraConfig(Enum):
    CAMERA_ID = DEFAULT_CAMERA_ID
    USE_THIS_CAMERA = True
    RESOLUTION = DEFAULT_RESOLUTION
    COLOR_CHANNELS: int = 3
    EXPOSURE: int = -7
    FRAMERATE: float = 30.0
    ROTATION: RotationTypes = RotationTypes.NO_ROTATION
    CAPTURE_FOURCC: str = "MJPG"  # TODO - consider other capture codecs
    WRITER_FOURCC: str = "MP4V"  # TODO - consider other writer codecs
