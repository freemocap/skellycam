from itertools import product

import numpy as np
import pytest

from skellycam.core import CameraId, BYTES_PER_PIXEL
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.detection.image_rotation_types import RotationTypes
from skellycam.tests.conftest import WeeImageShapes

# parameter options
camera_ids = [0, 1, "2", 3.0, CameraId(4)]
resolutions = list(WeeImageShapes)
rotations = list(RotationTypes)

all_combinations = list(
    product(camera_ids,
            resolutions,
            rotations,
            ))

parametrization_config = (
    "camera_id,resolution, rotation",
    all_combinations

)


@pytest.fixture
def test_default_camera_config():
    assert CameraConfig()


@pytest.mark.parametrize(*parametrization_config)
def test_custom_config(camera_id,
                       resolution,
                       rotation,
                       use_this_camera: bool = True,
                       exposure: int = -7,
                       framerate: float = 30,
                       capture_fourcc: str = "MJPG",
                       writer_fourcc: str = "MP4V",
                       ):
    input_resolution = ImageResolution(height=resolution.value[0], width=resolution.value[1])

    if len(resolution.value) == 3:
        number_of_color_channels = resolution.value[2]
        image_shape = (resolution.value[0], resolution.value[1], resolution.value[2])
    else:
        number_of_color_channels = 1
        image_shape = (resolution.value[0], resolution.value[1], 1)

    config = CameraConfig(
        camera_id=camera_id,
        use_this_camera=use_this_camera,
        resolution=input_resolution,
        color_channels=number_of_color_channels,
        exposure=exposure,
        framerate=framerate,
        rotation=rotation,
        capture_fourcc=capture_fourcc,
        writer_fourcc=writer_fourcc,
    )
    assert config.camera_id == CameraId(camera_id)
    assert config.use_this_camera == use_this_camera
    assert config.resolution == ImageResolution(height=resolution.value[0], width=resolution.value[1])
    assert config.color_channels == number_of_color_channels
    assert config.exposure == exposure
    assert config.framerate == framerate
    assert config.rotation == rotation
    assert config.capture_fourcc == capture_fourcc
    assert config.writer_fourcc == writer_fourcc
    assert config.orientation == "landscape" if resolution.value[1] > resolution.value[0] else "portrait"
    assert config.aspect_ratio == resolution.value[1] / resolution.value[0]
    assert config.image_shape == image_shape
    assert config.color_channels == number_of_color_channels
    assert config.image_size_bytes == np.prod(resolution.value) * BYTES_PER_PIXEL
    assert "BASE CONFIG" in str(config)
