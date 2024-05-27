from typing import Dict

import pytest

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config_model import CameraConfigs
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
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
                                                 shared_memory_names=existing_shared_memory_names_fixture)
    assert isinstance(manager, CameraSharedMemoryManager)
    assert len(manager.camera_shms) == len(camera_configs_fixture)


def test_shared_memory_names_property(camera_shared_memory_manager_fixture: CameraSharedMemoryManager):
    manager = camera_shared_memory_manager_fixture
    shared_memory_names = manager.shared_memory_names
    assert isinstance(shared_memory_names, Dict)
    for shm_name in shared_memory_names.values():
        assert isinstance(shm_name, SharedMemoryNames)


def test_get_multi_frame_payload(camera_shared_memory_manager_fixture: CameraSharedMemoryManager,
                                 multi_frame_payload_fixture: MultiFramePayload):
    manager = camera_shared_memory_manager_fixture
    for camera_id, camera_shm in manager.camera_shms.items():
        camera_shm.put_new_frame(image=multi_frame_payload_fixture.frames[camera_id].image,
                                 metadata=multi_frame_payload_fixture.frames[camera_id].metadata)

    # Test initial payload
    payload = manager.get_multi_frame_payload(payload=None)
    assert payload.full
    assert payload.multi_frame_number == 0

    # Test subsequent payload
    payload = manager.get_multi_frame_payload(payload=payload)
    assert payload.full
    assert payload.multi_frame_number == 1
    assert payload.utc_ns_to_perf_ns == multi_frame_payload_fixture.utc_ns_to_perf_ns

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
