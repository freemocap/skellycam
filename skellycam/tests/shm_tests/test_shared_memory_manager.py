from typing import Dict

import pytest

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.frames.models.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.frames.models.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory


@pytest.fixture
def camera_shared_memory_manager_fixture(camera_configs_fixture: CameraConfigs):
    return CameraGroupSharedMemory.create(camera_configs=camera_configs_fixture)


def test_create_camera_shared_memory_manager(camera_configs_fixture: CameraConfigs):
    manager = CameraGroupSharedMemory.create(camera_configs=camera_configs_fixture)
    assert isinstance(manager, CameraGroupSharedMemory)
    assert len(manager.camera_shms) == len(camera_configs_fixture)


def test_recreate_camera_shared_memory_manager(camera_shared_memory_manager_fixture: CameraGroupSharedMemory):
    recreated_manager = CameraGroupSharedMemory.recreate(
        camera_configs=camera_shared_memory_manager_fixture.camera_configs,
        group_shm_names=camera_shared_memory_manager_fixture.shared_memory_names)
    assert isinstance(recreated_manager, CameraGroupSharedMemory)
    assert len(recreated_manager.camera_shms) == len(camera_shared_memory_manager_fixture.camera_shms)


def test_shared_memory_names_property(camera_shared_memory_manager_fixture: CameraGroupSharedMemory):
    manager = camera_shared_memory_manager_fixture
    shared_memory_names = manager.shared_memory_names
    assert isinstance(shared_memory_names, Dict)
    for shm_name in shared_memory_names.values():
        assert isinstance(shm_name, SharedMemoryNames)


def test_get_multi_frame_payload(camera_shared_memory_manager_fixture: CameraGroupSharedMemory,
                                 multi_frame_payload_fixture: MultiFramePayload):
    manager = camera_shared_memory_manager_fixture
    assert manager.camera_ids == multi_frame_payload_fixture.camera_ids

    for camera_id, camera_shm in manager.camera_shms.items():
        metadata = multi_frame_payload_fixture.frames[camera_id].metadata
        metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_id
        camera_shm.put_new_frame(image=multi_frame_payload_fixture.frames[camera_id].image,
                                 metadata=metadata)

    # Test initial payload
    initial_payload = manager.get_multi_frame_payload(previous_payload=None)
    assert initial_payload.full
    assert initial_payload.multi_frame_number == 0

    # Test subsequent payload
    for camera_id, camera_shm in manager.camera_shms.items():
        camera_shm.put_new_frame(image=initial_payload.frames[camera_id].image,
                                 metadata=initial_payload.frames[camera_id].metadata)
    next_payload = manager.get_multi_frame_payload(previous_payload=initial_payload)
    assert next_payload.full
    assert next_payload.multi_frame_number == 1
    assert next_payload.utc_ns_to_perf_ns == initial_payload.utc_ns_to_perf_ns


def test_get_camera_shared_memory(camera_shared_memory_manager_fixture: CameraGroupSharedMemory,
                                  camera_configs_fixture: CameraConfigs):
    manager = camera_shared_memory_manager_fixture
    for camera_id in camera_configs_fixture.keys():
        camera_shm = manager.get_camera_shared_memory(camera_id)
        assert isinstance(camera_shm, CameraSharedMemory)


def test_close_and_unlink(camera_shared_memory_manager_fixture: CameraGroupSharedMemory):
    manager = camera_shared_memory_manager_fixture
    manager.close_and_unlink()

    for camera_shm in manager.camera_shms.values():
        # Test for image_shm
        image_shm_exception_raised = False
        try:
            camera_shm.image_shm.shm.buf[:]
        except TypeError:
            image_shm_exception_raised = True
        assert image_shm_exception_raised, "TypeError was not raised for image_shm"

        # Test for metadata_shm
        metadata_shm_exception_raised = False
        try:
            camera_shm.metadata_shm.shm.buf[:]
        except TypeError:
            metadata_shm_exception_raised = True
        assert metadata_shm_exception_raised, "TypeError was not raised for metadata_shm"
