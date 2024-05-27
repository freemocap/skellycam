import os
import time
from typing import Tuple

import numpy as np
import pytest
from _pytest.terminal import TerminalReporter
from fastapi import FastAPI
from starlette.testclient import TestClient

from skellycam.api.app_factory import create_app
from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.cameras.config.default_config import DEFAULT_CAMERA_ID, DEFAULT_IMAGE_SHAPE
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.frames.frame_metadata import FRAME_METADATA_SHAPE, FRAME_METADATA_DTYPE, FRAME_METADATA_MODEL
from skellycam.core.frames.frame_payload import FramePayloadDTO
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

TEST_ENV_NAME = 'TEST_ENV'


@pytest.fixture(scope='session', autouse=True)
def set_test_env_variable() -> None:
    # Set the environment variable before any tests run
    # TODO - make a better way to set the runtime environment - we'll want `testing` (running tests), `development`(running from source), and `production` (running from a built package, i.e. from pypi or a wheel file)
    os.environ[TEST_ENV_NAME] = 'true'
    yield
    # Clean up the environment variable after all tests have run
    del os.environ[TEST_ENV_NAME]


def pytest_terminal_summary(terminalreporter: TerminalReporter) -> None:
    """
    This hook is called after the whole test run finishes,
    you can use it to add a summary to the terminal output.
    """
    for report in terminalreporter.getreports("failed"):
        if report.location:
            file_path, line_num, _ = report.location
            terminalreporter.write_line(f"FAILED {file_path}:{line_num} - {report.longrepr}")
        else:
            terminalreporter.write_line(f"FAILED {report.longrepr}")


@pytest.fixture(
    params=[
        (12,),  # 1D
        (12, 2),  # 2D
        (12, 4, 4),  # 3D
        (12, 2, 8, 4),  # 4D
    ]
)
def ndarray_shape_fixture(request: pytest.fixture) -> Tuple[int, ...]:
    return request.param


@pytest.fixture(params=[np.uint8,
                        np.uint64,
                        np.int8,
                        int,
                        ])
def dtype_fixture(request: pytest.fixture) -> np.dtype:
    return request.param


@pytest.fixture(params=[DEFAULT_IMAGE_SHAPE,
                        (12, 15, 3),  # landscape
                        (13, 4, 3),  # portrait
                        (10, 10, 3),  # square
                        (12, 15, 1),  # landscape grayscale
                        (9, 5, 1),  # portrait grayscale
                        (4, 4, 1),  # square grayscale
                        # TODO - support monocolor images with no color channels
                        # (48, 64),  # square grayscale (no color channels)
                        # (64, 48),  # square grayscale (no color channels)
                        # (48, 48),  # square grayscale (no color channels)
                        ])
def image_shape_fixture(request: pytest.fixture) -> Tuple[int, int, int]:
    return request.param


@pytest.fixture()
def numpy_array_definition_fixture(ndarray_shape_fixture,
                                   dtype_fixture: np.dtype) -> Tuple[Tuple[int, ...], np.dtype]:
    return ndarray_shape_fixture, dtype_fixture


@pytest.fixture()
def random_array_fixture(numpy_array_definition_fixture: Tuple[Tuple[int, ...], np.dtype]) -> np.ndarray:
    shape, dtype = numpy_array_definition_fixture
    min_val = np.iinfo(dtype).min
    max_val = np.iinfo(dtype).max

    # Create the array and fill it with random values
    random_array = np.random.randint(min_val, max_val, size=shape, dtype=dtype)

    return random_array


@pytest.fixture()
def image_fixture(image_shape_fixture: Tuple[int, int, int]) -> np.ndarray:
    shape = image_shape_fixture
    return np.random.randint(0, 256, size=shape, dtype=np.uint8)


@pytest.fixture(params=[0, 1, 10, 1e5])
def frame_metadata_fixture(request: pytest.fixture) -> np.ndarray:
    metadata_array = np.ndarray(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)
    metadata_array[:] = time.perf_counter_ns()
    metadata_array[FRAME_METADATA_MODEL.CAMERA_ID.value] = DEFAULT_CAMERA_ID
    metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value] = request.param
    return metadata_array


@pytest.fixture()
def frame_payload_dto_fixture(image_fixture: np.ndarray,
                              frame_metadata_fixture: np.ndarray) -> FramePayloadDTO:
    dto = FramePayloadDTO(image=image_fixture, metadata=frame_metadata_fixture)
    assert dto
    assert dto.image.shape == image_fixture.shape
    assert np.array_equal(dto.image, image_fixture)
    assert np.array_equal(dto.metadata, frame_metadata_fixture)
    return dto


@pytest.fixture(params=[1, "2", 1e3])
def camera_id_fixture(request: pytest.fixture) -> CameraId:
    return CameraId(request.param)


@pytest.fixture()
def default_camera_config_fixture() -> CameraConfig:
    return CameraConfig()


@pytest.fixture()
def camera_config_fixture(camera_id_fixture: CameraId,
                          image_shape_fixture: Tuple[int, int, int]) -> CameraConfig:
    resolution = ImageResolution(height=image_shape_fixture[0], width=image_shape_fixture[1])
    return CameraConfig(camera_id=camera_id_fixture, resolution=resolution)


@pytest.fixture(params=[[0], [0, "2"], [1e3]])
def camera_configs_fixture(request: pytest.fixture,
                           image_shape_fixture: Tuple[int, int, int]
                           ) -> CameraConfigs:
    camera_configs = {}
    for cam_id in request.param:
        resolution = ImageResolution(height=image_shape_fixture[0], width=image_shape_fixture[1])
        camera_configs[CameraId(cam_id)] = CameraConfig(camera_id=CameraId(cam_id),
                                                        resolution=resolution)
    return camera_configs


@pytest.fixture()
def multi_frame_payload_fixture(camera_configs_fixture: CameraConfigs,
                                frame_payload_dto_fixture: FramePayloadDTO) -> MultiFramePayload:
    multi_frame_payload = MultiFramePayload.create_initial(camera_ids=list(camera_configs_fixture.keys()))
    for camera_id in camera_configs_fixture.keys():
        frame_payload_dto_fixture.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_id
        multi_frame_payload.add_frame(frame_payload_dto_fixture)
    assert multi_frame_payload.full
    return multi_frame_payload


@pytest.fixture
def single_camera_triggers_fixture(camera_id_fixture: CameraId) -> SingleCameraTriggers:
    return SingleCameraTriggers.from_camera_id(camera_id_fixture)


@pytest.fixture
def multi_camera_triggers_fixture(camera_configs_fixture: CameraConfigs) -> MultiCameraTriggerOrchestrator:
    return MultiCameraTriggerOrchestrator.from_camera_configs(camera_configs_fixture)


@pytest.fixture
def camera_shared_memory_fixture(camera_configs_fixture: CameraConfigs,
                                 ) -> Tuple[CameraSharedMemoryManager, CameraSharedMemoryManager]:
    manager = CameraSharedMemoryManager.create(camera_configs=camera_configs_fixture)
    assert manager
    recreated_manager = CameraSharedMemoryManager.recreate(camera_configs=camera_configs_fixture,
                                                           shared_memory_names=manager.shared_memory_names
                                                           )
    yield manager, recreated_manager

    manager.close_and_unlink()
    recreated_manager.close_and_unlink()


@pytest.fixture
def app_fixture() -> FastAPI:
    return create_app()


@pytest.fixture
def client_fixture(app_fixture: FastAPI) -> TestClient:
    with TestClient(app_fixture) as client:
        yield client

# @pytest.fixture
# def fronted_image_payload_fixture(multi_frame_payload_fixture: MultiFramePayload) -> FrontendImagePayload:
#     fe_payload = FrontendImagePayload.from_multi_frame_payload(multi_frame_payload_fixture)
#     assert fe_payload.multi_frame_number == multi_frame_payload_fixture.multi_frame_number
#     assert fe_payload.utc_ns_to_perf_ns == multi_frame_payload_fixture.utc_ns_to_perf_ns
#     assert fe_payload.camera_ids == multi_frame_payload_fixture.camera_ids
#     assert str(fe_payload)
#     return fe_payload
#
#
