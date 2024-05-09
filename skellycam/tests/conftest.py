import enum

import numpy as np
import pytest

from skellycam.core.frames.frame_payload import FramePayload


class ImageShape(enum.Enum):
    RGB_LANDSCAPE = (480, 640, 3)
    RGB_PORTRAIT = (640, 480, 3)
    MONO = (480, 640)
    SQUARE_RGB = (640, 640, 3)
    SQUARE_MONO = (640, 640)
    RGB_720P = (720, 1280, 3)
    RGB_1080P = (1080, 1920, 3)
    RGB_4K = (2160, 3840, 3)

test_images = {shape: np.random.randint(0, 256, size=shape.value, dtype=np.uint8) for shape in ImageShape}

@pytest.fixture(params=ImageShape)
def image_fixture(request) -> np.ndarray:
    return test_images[request.param]


