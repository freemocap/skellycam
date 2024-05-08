
import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.detection.image_rotation_types import RotationTypes

@pytest.fixture
def default_camera_config():
    return CameraConfig()

@pytest.fixture
def custom_camera_config():
    return CameraConfig(
        camera_id= CameraId(1),
        use_this_camera=False,
        resolution=ImageResolution(width=640, height=480),
        color_channels=1,
        exposure=5,
        framerate=60.0,
        rotation=RotationTypes.CLOCKWISE_90,
        capture_fourcc='H264',
        writer_fourcc='XVID'
    )

def test_default_initialization(default_camera_config):
    # Test default values
    assert default_camera_config.camera_id == CameraId(0)
    assert default_camera_config.use_this_camera is True
    # ... continue for other default values

def test_custom_initialization(custom_camera_config):
    # Test custom values
    assert custom_camera_config.camera_id ==  CameraId(1)
    assert custom_camera_config.use_this_camera is False
    assert custom_camera_config.resolution.width == 640
    assert custom_camera_config.resolution.height == 480
    assert custom_camera_config.color_channels == 1
    assert custom_camera_config.exposure == 5
    assert custom_camera_config.framerate == 60.0
    assert custom_camera_config.rotation == RotationTypes.CLOCKWISE_90
    assert custom_camera_config.capture_fourcc == 'H264'
    assert custom_camera_config.writer_fourcc == 'XVID'
    assert custom_camera_config.orientation == 'landscape'
    assert custom_camera_config.aspect_ratio == 640 / 480