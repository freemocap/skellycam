from typing import Dict

import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


@pytest.fixture
def camera_shared_memory_manager_fixture(camera_configs_fixture: CameraConfigs):
    return CameraSharedMemoryManager.create(camera_configs=camera_configs_fixture)


def test_create_camera_shared_memory_manager(camera_configs_fixture: CameraConfigs):
    manager = CameraSharedMemoryManager.create(camera_configs=camera_configs_fixture)
    assert isinstance(manager, CameraSharedMemoryManager)
    assert len(manager.camera_shms) == len(camera_configs_fixture)


def test_recreate_camera_shared_memory_manager(camera_configs_fixture: CameraConfigs,
                                               existing_shared_memory_names_fixture: Dict[CameraId, SharedMemoryNames]):
    manager = CameraSharedMemoryManager.recreate(camera_configs=camera_configs_fixture,
                                                 existing_shared_memory_names=existing_shared_memory_names_fixture)
    assert isinstance(manager, CameraSharedMemoryManager)
    assert len(manager.camera_shms) == len(camera_configs_fixture)


def test_shared_memory_names_property(camera_shared_memory_manager_fixture: CameraSharedMemoryManager):
    manager = camera_shared_memory_manager_fixture
    shared_memory_names = manager.shared_memory_names
    assert isinstance(shared_memory_names, Dict)
    for shm_name in shared_memory_names.values():
        assert isinstance(shm_name, SharedMemoryNames)


def test_get_multi_frame_payload(camera_shared_memory_manager_fixture: CameraSharedMemoryManager):
    manager = camera_shared_memory_manager_fixture
    payload = manager.get_multi_frame_payload()
    assert payload.full


def test_get_camera_shared_memory(camera_shared_memory_manager_fixture: CameraSharedMemoryManager,
                                  camera_configs_fixture: CameraConfigs):
    manager = camera_shared_memory_manager_fixture
    for camera_id in camera_configs_fixture.keys():
        camera_shm = manager.get_camera_shared_memory(camera_id)
        assert isinstance(camera_shm, CameraSharedMemory)


def test_close_and_unlink(camera_shared_memory_manager_fixture: CameraSharedMemoryManager):
    manager = camera_shared_memory_manager_fixture
    manager.close_and_unlink()
    for camera_shm in manager.camera_shms.values():
        with pytest.raises(FileNotFoundError):
            camera_shm.image_shm.shm.buf[:]
        with pytest.raises(FileNotFoundError):
            camera_shm.metadata_shm.shm.buf[:]
