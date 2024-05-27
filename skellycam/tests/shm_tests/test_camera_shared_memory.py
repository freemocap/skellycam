from typing import Tuple

import numpy as np
import pytest

from skellycam.core import IMAGE_DATA_DTYPE
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_SHAPE, FRAME_METADATA_DTYPE
from skellycam.core.frames.frame_payload import FramePayloadDTO
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory
from skellycam.core.memory.shared_memory_element import SharedMemoryElement


def make_dummy_image_from_shape(shape: Tuple[int, ...]) -> np.ndarray:
    return np.random.randint(0, 256, size=shape, dtype=np.uint8)


def test_create_camera_shared_memory(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)
    assert isinstance(camera_shm, CameraSharedMemory)
    assert camera_shm.image_shm.buffer.shape == camera_config_fixture.image_shape
    assert camera_shm.metadata_shm.buffer.shape == FRAME_METADATA_SHAPE

    camera_shm.close()
    camera_shm.unlink()


def test_recreate_camera_shared_memory(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config_fixture)
    shm_names = camera_shm.shared_memory_names

    recreated_camera_shm = CameraSharedMemory.recreate(camera_config=camera_config_fixture,
                                                       shared_memory_names=shm_names)
    assert isinstance(recreated_camera_shm, CameraSharedMemory)
    assert recreated_camera_shm.image_shm.buffer.shape == camera_config_fixture.image_shape
    assert recreated_camera_shm.metadata_shm.buffer.shape == FRAME_METADATA_SHAPE

    camera_shm.close()
    recreated_camera_shm.close()
    camera_shm.unlink()


def test_put_and_retrieve_frame(camera_config_fixture: CameraConfig,
                                frame_metadata_fixture: np.ndarray) -> None:
    image = make_dummy_image_from_shape(camera_config_fixture.image_shape)
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)

    camera_shm.put_new_frame(image=image, metadata=frame_metadata_fixture)
    frame_dto = camera_shm.retrieve_frame()
    assert isinstance(frame_dto, FramePayloadDTO)
    assert np.array_equal(frame_dto.image, image)
    assert np.array_equal(frame_dto.frame_metadata, frame_metadata_fixture)

    camera_shm.close()
    camera_shm.unlink()


def test_close_and_unlink(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)

    camera_shm.close()
    camera_shm.unlink()

    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(shm_name=camera_shm.shared_memory_names.image_shm_name,
                                     shape=camera_config_fixture.image_shape,
                                     dtype=IMAGE_DATA_DTYPE)
    with pytest.raises(FileNotFoundError):
        SharedMemoryElement.recreate(shm_name=camera_shm.shared_memory_names.metadata_shm_name,
                                     shape=FRAME_METADATA_SHAPE,
                                     dtype=FRAME_METADATA_DTYPE)


def test_integration_workflow(camera_config_fixture: CameraConfig,
                              frame_metadata_fixture: np.ndarray, ) -> None:
    image = make_dummy_image_from_shape(camera_config_fixture.image_shape)
    # Create CameraSharedMemory and put frame
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)
    camera_shm.put_new_frame(image=image, metadata=frame_metadata_fixture)

    # Recreate CameraSharedMemory and retrieve frame
    shm_names = camera_shm.shared_memory_names
    recreated_camera_shm = CameraSharedMemory.recreate(camera_config=camera_config_fixture,
                                                       shared_memory_names=shm_names)
    frame_dto = recreated_camera_shm.retrieve_frame()

    assert isinstance(frame_dto, FramePayloadDTO)
    assert np.array_equal(frame_dto.image, image)
    assert np.array_equal(frame_dto.frame_metadata, frame_metadata_fixture)

    # Cleanup
    camera_shm.close()
    camera_shm.unlink()
    recreated_camera_shm.close()
    recreated_camera_shm.unlink()
