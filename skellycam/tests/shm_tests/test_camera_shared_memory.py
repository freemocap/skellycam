import numpy as np
import pytest

from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory
from skellycam.core.memory.shared_memory_element import SharedMemoryElement


def test_create_camera_shared_memory(camera_config):
    camera_shm = CameraSharedMemory.create(camera_config)
    assert isinstance(camera_shm, CameraSharedMemory)
    assert camera_shm.image_shm.buffer.shape == camera_config.image_shape
    assert camera_shm.metadata_shm.buffer.shape == FRAME_METADATA_MODEL.shape

    camera_shm.close()
    camera_shm.unlink()


def test_recreate_camera_shared_memory(camera_config):
    camera_shm = CameraSharedMemory.create(camera_config)
    shm_names = camera_shm.shared_memory_names

    recreated_camera_shm = CameraSharedMemory.recreate(camera_config, shm_names)
    assert isinstance(recreated_camera_shm, CameraSharedMemory)
    assert recreated_camera_shm.image_shm.buffer.shape == camera_config.image_shape
    assert recreated_camera_shm.metadata_shm.buffer.shape == FRAME_METADATA_MODEL.shape

    camera_shm.close()
    camera_shm.unlink()
    recreated_camera_shm.close()


def test_put_and_retrieve_frame(camera_config, frame_data):
    camera_shm = CameraSharedMemory.create(camera_config)
    image, metadata = frame_data

    camera_shm.put_new_frame(image, metadata)
    frame_view = camera_shm.retrieve_frame_memoryview()

    assert np.array_equal(frame_view.image, image)
    assert np.array_equal(frame_view.metadata, metadata)

    camera_shm.close()
    camera_shm.unlink()


def test_close_and_unlink(camera_config):
    camera_shm = CameraSharedMemory.create(camera_config)

    camera_shm.close()
    camera_shm.unlink()

    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(camera_shm.image_shm.name, camera_config.image_shape, np.uint8)


def test_integration_workflow(camera_config, frame_data):
    # Create CameraSharedMemory and put frame
    camera_shm = CameraSharedMemory.create(camera_config)
    image, metadata = frame_data
    camera_shm.put_new_frame(image, metadata)

    # Recreate CameraSharedMemory and retrieve frame
    shm_names = camera_shm.shared_memory_names
    recreated_camera_shm = CameraSharedMemory.recreate(camera_config, shm_names)
    frame_view = recreated_camera_shm.retrieve_frame_memoryview()

    assert np.array_equal(frame_view.image, image)
    assert np.array_equal(frame_view.metadata, metadata)

    # Cleanup
    camera_shm.close()
    camera_shm.unlink()
    recreated_camera_shm.close()
