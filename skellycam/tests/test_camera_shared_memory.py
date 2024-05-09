from multiprocessing import Lock

import numpy as np
import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager




@pytest.fixture
def image_fixture() -> np.ndarray:
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def original_shared_memory_manager_fixture(camera_configs_fixture, lock_fixture) -> CameraSharedMemoryManager:
    return CameraSharedMemoryManager(camera_configs=camera_configs_fixture, lock=lock_fixture)


@pytest.fixture
def shared_memory_name_fixture(original_shared_memory_manager_fixture) -> str:
    return original_shared_memory_manager_fixture.shared_memory_names[CameraId(0)]


@pytest.fixture
def recreated_shared_memory_manager_fixture(camera_configs_fixture, lock_fixture,
                                            shared_memory_name_fixture) -> CameraSharedMemoryManager:
    return CameraSharedMemoryManager(camera_configs=camera_configs_fixture,
                                     lock=lock_fixture,
                                     existing_shared_memory_names={CameraId(0): shared_memory_name_fixture})


@pytest.fixture
def original_camera_shared_memory_fixture(original_shared_memory_manager_fixture) -> CameraSharedMemory:
    return original_shared_memory_manager_fixture.get_camera_shared_memory(CameraId(0))


@pytest.fixture
def recreated_camera_shared_memory_fixture(recreated_shared_memory_manager_fixture) -> CameraSharedMemory:
    return recreated_shared_memory_manager_fixture.get_camera_shared_memory(CameraId(0))


def test_put_frame(original_camera_shared_memory_fixture,
                   recreated_camera_shared_memory_fixture,
                   frame_payload_fixture, image_fixture):
    # put frame
    original_camera_shared_memory_fixture.put_frame(frame_payload_fixture,
                                                    image_fixture)
    # TODO - add an `initialization` flag so we can detect the first frame written

    # put another frame
    original_camera_shared_memory_fixture.put_frame(frame_payload_fixture,
                                                    image_fixture)
    assert original_camera_shared_memory_fixture.new_frame_available
    assert original_camera_shared_memory_fixture.last_frame_written_index == 1
    assert recreated_camera_shared_memory_fixture.new_frame_available
    assert recreated_camera_shared_memory_fixture.last_frame_written_index == 1

    # retrieve frame
    assert recreated_camera_shared_memory_fixture.frame_to_read == 0
    retrieved_frame = recreated_camera_shared_memory_fixture.get_next_frame()
    assert retrieved_frame.dict(exclude={"image_data"}) == frame_payload_fixture.dict(exclude={"image_data"})
    assert np.sum(retrieved_frame.image ) == np.sum(image_fixture)
    assert not recreated_camera_shared_memory_fixture.new_frame_available

    # retrieve another frame
    retrieved_frame2 = recreated_camera_shared_memory_fixture.get_next_frame()
    assert recreated_camera_shared_memory_fixture.frame_to_read == 1
    assert not recreated_camera_shared_memory_fixture.new_frame_available
    assert not original_camera_shared_memory_fixture.new_frame_available


def test_loop_around(original_camera_shared_memory_fixture,
                     recreated_camera_shared_memory_fixture,
                     frame_payload_fixture, image_fixture):
    for loop in range(256 * 2):
        original_camera_shared_memory_fixture.put_frame(frame_payload_fixture, image_fixture)
        assert original_camera_shared_memory_fixture.new_frame_available
        assert original_camera_shared_memory_fixture.last_frame_written_index == loop % 256
        assert recreated_camera_shared_memory_fixture.new_frame_available
        assert recreated_camera_shared_memory_fixture.frame_to_read == loop % 256
        frame = recreated_camera_shared_memory_fixture.get_next_frame()
        assert frame == frame_payload_fixture


