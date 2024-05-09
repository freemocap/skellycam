import enum
from asyncio import Lock

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frame_payload import FramePayload


class TestImageShapes(enum.Enum):
    RGB_LANDSCAPE = (480, 640, 3)
    RGB_PORTRAIT = (640, 480, 3)
    MONO_2 = (480, 640)
    MONO_3 = (480, 640, 1)
    SQUARE_RGB = (640, 640, 3)
    SQUARE_MONO = (640, 640)
    RGB_720P = (720, 1280, 3)
    RGB_1080P = (1080, 1920, 3)
    RGB_4K = (2160, 3840, 3)


test_images = {shape: np.random.randint(0, 256, size=shape.value, dtype=np.uint8) for shape in TestImageShapes}


@pytest.fixture(params=TestImageShapes)
def image_fixture(request) -> np.ndarray:
    return test_images[request.param]

@pytest.fixture(params=[0, "1", 2.0])
def camera_configs_fixture(request) -> CameraConfigs:
    configs = CameraConfigs(request.param)
    return configs


@pytest.fixture
def lock_fixture() -> Lock:
    return Lock()


@pytest.fixture
def frame_payload_fixture() -> FramePayload:
    return FramePayload.create_hydrated_dummy(make_image=False)
