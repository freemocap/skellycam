from typing import Tuple

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, FrameMemoryView
from skellycam.core.memory.shared_memory_element import SharedMemoryElement


def test_create_camera_shared_memory(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)
    assert isinstance(camera_shm, CameraSharedMemory)
    assert camera_shm.image_shm.buffer.shape == camera_config_fixture.image_shape
    assert camera_shm.metadata_shm.buffer.shape == FRAME_METADATA_MODEL.shape

    camera_shm.close()
    camera_shm.unlink()


def test_recreate_camera_shared_memory(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config_fixture)
    shm_names = camera_shm.shared_memory_names

    recreated_camera_shm = CameraSharedMemory.recreate(camera_config=camera_config_fixture,
                                                       shared_memory_names=shm_names)
    assert isinstance(recreated_camera_shm, CameraSharedMemory)
    assert recreated_camera_shm.image_shm.buffer.shape == camera_config_fixture.image_shape
    assert recreated_camera_shm.metadata_shm.buffer.shape == FRAME_METADATA_MODEL.shape

    camera_shm.close()
    camera_shm.unlink()
    recreated_camera_shm.close()


def test_put_and_retrieve_frame(camera_config_fixture: CameraConfig,
                                frame_data_fixture: Tuple[np.ndarray, np.ndarray]) -> None:
    image, metadata = frame_data_fixture
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)

    camera_shm.put_new_frame(image=image, metadata=metadata)
    frame_view = camera_shm.retrieve_frame_memoryview()
    assert isinstance(frame_view, FrameMemoryView)
    assert np.array_equal(frame_view.image, image)
    assert np.array_equal(frame_view.metadata, metadata)

    camera_shm.close()
    camera_shm.unlink()


def test_close_and_unlink(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)

    camera_shm.close()
    camera_shm.unlink()

    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(camera_shm.shared_memory_names.image_shm_name,
                                     camera_config_fixture.image_shape,
                                     camera_config_fixture.image_dtype)
    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(camera_shm.shared_memory_names.metadata_shm_name,
                                     FRAME_METADATA_MODEL.shape,
                                     FRAME_METADATA_MODEL.dtype)


def test_integration_workflow(camera_config_fixture: CameraConfig,
                              frame_data_fixture: Tuple[np.ndarray, np.ndarray]) -> None:
    image, metadata = frame_data_fixture
    # Create CameraSharedMemory and put frame
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)
    camera_shm.put_new_frame(image=image, metadata=metadata)

    # Recreate CameraSharedMemory and retrieve frame
    shm_names = camera_shm.shared_memory_names
    recreated_camera_shm = CameraSharedMemory.recreate(camera_config=camera_config_fixture,
                                                       shared_memory_names=shm_names)
    frame_view = recreated_camera_shm.retrieve_frame_memoryview()

    assert isinstance(frame_view, FrameMemoryView)
    assert np.array_equal(frame_view.image, image)
    assert np.array_equal(frame_view.metadata, metadata)

    # Cleanup
    assert camera_shm.image_shm.shm is not None
    assert camera_shm.metadata_shm.shm is not None
    camera_shm.close()
    assert camera_shm.image_shm.shm is None
    assert camera_shm.metadata_shm.shm is None
    camera_shm.unlink()
    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(camera_shm.shared_memory_names.image_shm_name,
                                     camera_config_fixture.image_shape,
                                     camera_config_fixture.image_dtype)
    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(camera_shm.shared_memory_names.metadata_shm_name,
                                     FRAME_METADATA_MODEL.shape,
                                     FRAME_METADATA_MODEL.dtype)

    assert recreated_camera_shm.image_shm.shm is not None
    assert recreated_camera_shm.metadata_shm.shm is not None
    recreated_camera_shm.close()
    assert recreated_camera_shm.image_shm.shm is None
    assert recreated_camera_shm.metadata_shm.shm is None
