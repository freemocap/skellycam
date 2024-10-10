from itertools import product

import pytest

from skellycam.core import CameraId, BYTES_PER_MONO_PIXEL
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera.config.default_config import DefaultCameraConfig
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes


def test_default_camera_config(default_camera_config_fixture: CameraConfig):
    c = default_camera_config_fixture
    assert c.camera_id == DefaultCameraConfig.CAMERA_ID.value
    assert c.use_this_camera == DefaultCameraConfig.USE_THIS_CAMERA.value
    assert c.resolution == DefaultCameraConfig.RESOLUTION.value
    assert c.color_channels == DefaultCameraConfig.COLOR_CHANNELS.value
    assert c.exposure == DefaultCameraConfig.EXPOSURE.value
    assert c.framerate == DefaultCameraConfig.FRAMERATE.value
    assert c.rotation == DefaultCameraConfig.ROTATION.value
    assert c.capture_fourcc == DefaultCameraConfig.CAPTURE_FOURCC.value
    assert c.writer_fourcc == DefaultCameraConfig.WRITER_FOURCC.value
    assert c.orientation == "landscape" if DefaultCameraConfig.RESOLUTION.value.width > DefaultCameraConfig.RESOLUTION.value.height else "portrait"
    assert c.aspect_ratio == DefaultCameraConfig.RESOLUTION.value.width / DefaultCameraConfig.RESOLUTION.value.height
    assert c.image_shape == (DefaultCameraConfig.RESOLUTION.value.height, DefaultCameraConfig.RESOLUTION.value.width,
                             DefaultCameraConfig.COLOR_CHANNELS.value)
    assert c.image_size_bytes == DefaultCameraConfig.RESOLUTION.value.height * DefaultCameraConfig.RESOLUTION.value.width * DefaultCameraConfig.COLOR_CHANNELS.value * BYTES_PER_MONO_PIXEL
    assert "BASE CONFIG" in str(c)


# Parameterization Configurations
camera_ids = [CameraId(0), CameraId(1)]
resolutions = [ImageResolution(height=720, width=1280),  # 720p landscape
               ImageResolution(height=1280, width=720),  # 720p portrait
               ImageResolution(height=1080, width=1920),  # 1080p landscape
               ImageResolution(height=1080, width=1080)]  # 1080p square
rotations = [RotationTypes.NO_ROTATION, RotationTypes.CLOCKWISE_90]
color_channels_options = [1, 3]

parametrization_config = list(product(camera_ids, resolutions, rotations, color_channels_options))


@pytest.mark.parametrize("camera_id,resolution,rotation,color_channels", parametrization_config)
def test_custom_config(camera_id: CameraId,
                       resolution: ImageResolution,
                       rotation: RotationTypes,
                       color_channels: int):
    config = CameraConfig(
        camera_id=camera_id,
        use_this_camera=True,
        resolution=resolution,
        color_channels=color_channels,
        exposure=-7,
        frame_rate=30,
        rotation=rotation,
        capture_fourcc="MJPG",
        writer_fourcc="MP4V",
    )
    assert config.camera_id == camera_id
    assert config.use_this_camera is True
    assert config.resolution == resolution
    assert config.color_channels == color_channels
    assert config.exposure == -7
    assert config.framerate == 30
    assert config.rotation == rotation
    assert config.capture_fourcc == "MJPG"
    assert config.writer_fourcc == "MP4V"
    assert config.orientation == "landscape" if resolution.width > resolution.height else "portrait"
    assert config.aspect_ratio == resolution.width / resolution.height
    expected_image_shape = (resolution.height, resolution.width, color_channels) if color_channels > 1 else (
        resolution.height, resolution.width)
    assert config.image_shape == expected_image_shape
    assert config.image_size_bytes == resolution.height * resolution.width * color_channels * BYTES_PER_MONO_PIXEL
    assert "BASE CONFIG" in str(config)
