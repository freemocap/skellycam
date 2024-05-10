import enum
import time
from typing import List, Tuple

import numpy as np
import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.frames.frame_payload import FramePayload


class TestImageShapes(enum.Enum):
    RGB_LANDSCAPE = (480, 640, 3)
    RGB_PORTRAIT = (640, 480, 3)
    SQUARE_RGB = (640, 640, 3)
    RGB_720P = (720, 1280, 3)
    RGB_1080P = (1080, 1920, 3)
    RGB_4K = (2160, 3840, 3)
    # TODO - Support monochrome images
    # MONO_2 = (480, 640)
    # MONO_3 = (480, 640, 1)
    # SQUARE_MONO = (640, 640)


test_images = {shape: np.random.randint(0, 256, size=shape.value, dtype=np.uint8) for shape in TestImageShapes}

test_camera_ids = [1, "2", CameraId(4),]


@pytest.fixture(params=[[0], test_camera_ids])
def camera_ids_fixture(request) -> List[CameraId]:
    return [CameraId(cam_id) for cam_id in request.param]


@pytest.fixture(params=TestImageShapes)
def image_fixture(request) -> np.ndarray:
    return test_images[request.param]


@pytest.fixture
def camera_configs_fixture(camera_ids_fixture: List[CameraId]) -> CameraConfigs:
    configs = CameraConfigs()
    if len(camera_ids_fixture) > 1:
        for camera_id in camera_ids_fixture[1:]:
            configs[camera_id] = CameraConfig(camera_id=camera_id)

    return configs

