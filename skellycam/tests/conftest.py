import enum
import multiprocessing
import time
from typing import List, Tuple

import numpy as np
import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.controller.controller import Controller
from skellycam.core.controller.singleton import get_or_create_controller
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


class TestFullSizeImageShapes(enum.Enum):
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


class TestImageShapes(enum.Enum):
    LANDSCAPE = (48, 64, 3)
    PORTRAIT = (64, 48, 3)
    SQUARE = (64, 64, 3)


test_images = {shape: np.random.randint(0, 256, size=shape.value, dtype=np.uint8) for shape in TestImageShapes}

test_camera_ids = [1, "2", CameraId(4), ]


@pytest.fixture(params=[[0], test_camera_ids])
def camera_ids_fixture(request) -> List[CameraId]:
    return [CameraId(cam_id) for cam_id in request.param]


@pytest.fixture(params=TestFullSizeImageShapes)
def full_size_image_fixture(request) -> np.ndarray:
    return test_images[request.param]


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


@pytest.fixture
def frame_payload_fixture(image_fixture: np.ndarray) -> FramePayload:
    # Arrange
    frame = FramePayload.create_empty(camera_id=CameraId(0),
                                      image_shape=image_fixture.shape,
                                      frame_number=0)
    frame.image = image_fixture
    frame.previous_frame_timestamp_ns = time.perf_counter_ns()
    frame.timestamp_ns = time.perf_counter_ns()
    frame.success = True
    # Assert
    for key, value in frame.dict().items():
        assert value is not None, f"Key {key} is None"
    assert frame.hydrated
    assert frame.image_shape == image_fixture.shape
    assert np.sum(frame.image - image_fixture) == 0
    return frame


@pytest.fixture
def shared_memory_fixture(camera_configs_fixture: CameraConfigs,
                          ) -> Tuple[CameraSharedMemoryManager, CameraSharedMemoryManager]:
    lock = multiprocessing.Lock()
    manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture, lock=lock)
    assert manager
    recreated_manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture,
                                                  lock=lock,
                                                  existing_shared_memory_names=manager.shared_memory_names
                                                  )
    return manager, recreated_manager


@pytest.fixture
def controller_fixture() -> Controller:
    return get_or_create_controller()
