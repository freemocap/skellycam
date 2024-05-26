from multiprocessing import shared_memory

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory


def test_create(camera_config_fixture: CameraConfig):
    cam_shm = CameraSharedMemory.create(camera_config_fixture)

    assert cam_shm is not None
    assert isinstance(cam_shm.image_buffer, np.ndarray)
    assert isinstance(cam_shm.metadata_buffer, np.ndarray)
    assert isinstance(cam_shm.image_shm, shared_memory.SharedMemory)
    assert isinstance(cam_shm.metadata_shm, shared_memory.SharedMemory)

    assert cam_shm.image_buffer.shape == camera_config_fixture.image_shape
    assert cam_shm.metadata_buffer.shape == FRAME_METADATA_MODEL.shape

    # Note: The size of the shared memory buffer may be larger than the size of the image
    # and metadata buffers because it is rounded up to the nearest multiple of the system page size
    assert cam_shm.image_shm.size >= camera_config_fixture.image_size_bytes
    assert cam_shm.metadata_shm.size >= FRAME_METADATA_MODEL.size_in_bytes

    cam_shm.close()
    cam_shm.unlink()


def test_recreate(camera_config_fixture: CameraConfig):
    cam_shm = CameraSharedMemory.create(camera_config_fixture)

    shared_memory_names = cam_shm.shared_memory_names

    cam_shm_recreated = CameraSharedMemory.recreate(camera_config_fixture, shared_memory_names)

    assert cam_shm_recreated is not None
    assert isinstance(cam_shm_recreated.image_buffer, np.ndarray)
    assert isinstance(cam_shm_recreated.metadata_buffer, np.ndarray)
    assert isinstance(cam_shm_recreated.image_shm, shared_memory.SharedMemory)
    assert isinstance(cam_shm_recreated.metadata_shm, shared_memory.SharedMemory)

    assert cam_shm_recreated.image_buffer.shape == camera_config_fixture.image_shape
    assert cam_shm_recreated.metadata_buffer.shape == FRAME_METADATA_MODEL.shape
    assert cam_shm_recreated.image_shm.size == camera_config_fixture.image_size_bytes
    cam_shm.close()
    cam_shm.unlink()
    cam_shm_recreated.close()
    cam_shm_recreated.unlink()


def test_put_new_frame(camera_config_fixture: CameraConfig):
    cam_shm = CameraSharedMemory.create(camera_config_fixture)

    image = np.zeros(camera_config_fixture.image_shape, dtype=np.uint8)
    metadata = np.zeros((FRAME_METADATA_MODEL.number_of_elements,), dtype=np.uint64)

    cam_shm.put_new_frame(image, metadata)

    assert np.array_equal(cam_shm.image_buffer, image)
    assert np.array_equal(cam_shm.metadata_buffer, metadata)

    cam_shm.close()
    cam_shm.unlink()


def test_retrieve_frame(camera_config_fixture: CameraConfig):
    cam_shm = CameraSharedMemory.create(camera_config_fixture)

    image = np.zeros(camera_config_fixture.image_shape, dtype=np.uint8)
    metadata = np.zeros((FRAME_METADATA_MODEL.number_of_elements,), dtype=np.uint64)

    cam_shm.put_new_frame(image, metadata)
    retrieved_image, retrieved_metadata = cam_shm.retrieve_frame()

    assert np.array_equal(retrieved_image, image)
    assert np.array_equal(retrieved_metadata, metadata)

    cam_shm.close()
    cam_shm.unlink()


def test_close(camera_config_fixture: CameraConfig):
    cam_shm = CameraSharedMemory.create(camera_config_fixture)

    cam_shm.close()
    assert not cam_shm.image_shm._is_open
    assert not cam_shm.metadata_shm._is_open

    cam_shm.unlink()


def test_unlink(camera_config_fixture: CameraConfig):
    cam_shm = CameraSharedMemory.create(camera_config_fixture)
    # Close and unlink the shared memory segments
    cam_shm.close()
    cam_shm.unlink()
    # Now, trying to access the shared memory by name should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        shared_memory.SharedMemory(name=cam_shm.image_shm.name)
    with pytest.raises(FileNotFoundError):
        shared_memory.SharedMemory(name=cam_shm.metadata_shm.name)


def test_integration_workflow(camera_config_fixture: CameraConfig):
    # Process 1: Create shared memory
    cam_shm_creator = CameraSharedMemory.create(camera_config_fixture)
    shared_memory_names = cam_shm_creator.shared_memory_names

    # Process 2: Recreate shared memory
    cam_shm_recreator = CameraSharedMemory.recreate(camera_config_fixture, shared_memory_names)

    # Process 1: Put new frame
    image = np.random.randint(0, 255, camera_config_fixture.image_shape, dtype=np.uint8)
    metadata = np.random.randint(0, 255, (FRAME_METADATA_MODEL.number_of_elements,), dtype=np.uint64)
    cam_shm_creator.put_new_frame(image, metadata)

    # Process 2: Retrieve frame
    retrieved_image, retrieved_metadata = cam_shm_recreator.retrieve_frame()

    assert np.array_equal(retrieved_image, image)
    assert np.array_equal(retrieved_metadata, metadata)

    cam_shm_creator.close()
    cam_shm_creator.unlink()
    cam_shm_recreator.close()
    cam_shm_recreator.unlink()
