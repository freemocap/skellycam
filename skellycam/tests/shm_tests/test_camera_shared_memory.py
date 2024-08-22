from typing import Tuple

import numpy as np

from skellycam.core import IMAGE_DATA_DTYPE
from skellycam.core.cameras.camera.config.camera_config import CameraConfig
from skellycam.core.frames.metadata.frame_metadata import FRAME_METADATA_SHAPE, FRAME_METADATA_DTYPE, \
    FRAME_METADATA_MODEL
from skellycam.core.frames.payload_models.frame_payload import FramePayloadDTO
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
    frame_metadata_fixture[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_config_fixture.camera_id
    camera_shm.put_new_frame(image=image, metadata=frame_metadata_fixture)
    frame_dto = camera_shm.retrieve_frame()
    assert isinstance(frame_dto, FramePayloadDTO)
    assert np.array_equal(frame_dto.image, image)
    assert frame_dto.metadata.shape == FRAME_METADATA_SHAPE
    assert frame_dto.metadata.dtype == FRAME_METADATA_DTYPE
    assert frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] == camera_config_fixture.camera_id

    camera_shm.close()
    camera_shm.unlink()


def test_close_and_unlink(camera_config_fixture: CameraConfig) -> None:
    camera_shm = CameraSharedMemory.create(camera_config=camera_config_fixture)

    camera_shm.close()
    camera_shm.unlink()

    # Test for image_shm
    image_shm_not_found_exception_raised = False
    try:
        SharedMemoryElement.recreate(shm_name=camera_shm.shared_memory_names.image_shm_name,
                                     shape=camera_config_fixture.image_shape,
                                     dtype=IMAGE_DATA_DTYPE)
    except FileNotFoundError:
        image_shm_not_found_exception_raised = True
    assert image_shm_not_found_exception_raised, "FileNotFoundError was not raised for image_shm"

    # Test for metadata_shm
    metadata_shm_not_found_exception_raised = False
    try:
        SharedMemoryElement.recreate(shm_name=camera_shm.shared_memory_names.metadata_shm_name,
                                     shape=FRAME_METADATA_SHAPE,
                                     dtype=FRAME_METADATA_DTYPE)
    except FileNotFoundError:
        metadata_shm_not_found_exception_raised = True
    assert metadata_shm_not_found_exception_raised, "FileNotFoundError was not raised for metadata_shm"


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
    assert frame_dto.metadata.shape == FRAME_METADATA_SHAPE
    assert frame_dto.metadata.dtype == FRAME_METADATA_DTYPE
    assert frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] == camera_config_fixture.camera_id

    # Cleanup
    camera_shm.close()
    camera_shm.unlink()
    recreated_camera_shm.close()
    recreated_camera_shm.unlink()
