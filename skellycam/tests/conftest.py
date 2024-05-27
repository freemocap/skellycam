import os
import time
from typing import Tuple

import numpy as np
import pytest
from _pytest.terminal import TerminalReporter

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_metadata import FRAME_METADATA_SHAPE, FRAME_METADATA_DTYPE

TEST_ENV_NAME = 'TEST_ENV'


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


@pytest.fixture(scope='session', autouse=True)
def set_test_env_variable() -> None:
    # Set the environment variable before any tests run
    # TODO - make a better way to set the runtime environment - we'll want `testing` (running tests), `development`(running from source), and `production` (running from a built package, i.e. from pypi or a wheel file)
    os.environ[TEST_ENV_NAME] = 'true'
    yield
    # Clean up the environment variable after all tests have run
    del os.environ[TEST_ENV_NAME]


@pytest.fixture(
    params=[
        (256,),  # 1D
        (256, 2),  # 2D
        (64, 4, 4),  # 3D
        (32, 2, 8, 4),  # 4D
    ]
)
def array_shape_fixture(request: pytest.fixture) -> Tuple[int, ...]:
    return request.param


@pytest.fixture(params=[np.uint8,
                        np.uint64,
                        np.int8,
                        np.int64,
                        int,
                        ])
def dtype_fixture(request: pytest.fixture) -> np.dtype:
    return request.param


@pytest.fixture()
def numpy_array_definition_fixture(array_shape_fixture: Tuple[int, ...],
                                   dtype_fixture: np.dtype) -> Tuple[Tuple[int, ...], np.dtype]:
    return array_shape_fixture, dtype_fixture


@pytest.fixture()
def frame_metadata_fixture() -> np.ndarray:
    metadata_array = np.ndarray(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)
    metadata_array[:] = time.perf_counter_ns()
    return metadata_array


@pytest.fixture()
def random_array_fixture(numpy_array_definition_fixture: Tuple[Tuple[int, ...], np.dtype]) -> np.ndarray:
    shape, dtype = numpy_array_definition_fixture
    min_val = np.iinfo(dtype).min
    max_val = np.iinfo(dtype).max

    # Create the array and fill it with random values
    random_array = np.random.randint(min_val, max_val, size=shape, dtype=dtype)

    return random_array


@pytest.fixture(params=[1, "2", 4, ])
def camera_id_fixture(request: pytest.fixture) -> CameraId:
    return CameraId(request.param)


@pytest.fixture()
def camera_config_fixture(camera_id_fixture: CameraId) -> CameraConfig:
    return CameraConfig(camera_id=camera_id_fixture)

# class WeeImageShapes(enum.Enum):
#     LANDSCAPE = (48, 64, 3)
#     PORTRAIT = (64, 48, 3)
#     SQUARE = (64, 64, 3)
#     #TODO - support monocolor images
#
#
# test_images = {shape: np.random.randint(0, 256, size=shape.value, dtype=np.uint8) for shape in WeeImageShapes}
#
#
# @pytest.fixture(params=WeeImageShapes)
# def image_fixture(request) -> np.ndarray:
#     return test_images[request.param]
#
#
#
#

#
#
# @pytest.fixture(params=[[0], test_camera_ids])
# def camera_ids_fixture(request) -> List[CameraId]:
#     return [CameraId(cam_id) for cam_id in request.param]
#
#
# @pytest.fixture(params=TestFullSizeImageShapes)
# def full_size_image_fixture(request) -> np.ndarray:
#     return test_images[request.param]
#
#
# @pytest.fixture
# def camera_configs_fixture(camera_ids_fixture: List[CameraId]) -> CameraConfigs:
#     configs = CameraConfigs()
#     if len(camera_ids_fixture) > 1:
#         for camera_id in camera_ids_fixture[1:]:
#             from skellycam.core.cameras.config.camera_config import CameraConfig
#             configs[camera_id] = CameraConfig(camera_id=camera_id)
#
#     return configs
#
#

#
# @pytest.fixture
# def single_camera_triggers_fixture(camera_id_fixture: "CameraId") -> SingleCameraTriggers:
#     return SingleCameraTriggers.from_camera_id(camera_id_fixture)
#
#
# @pytest.fixture
# def multi_camera_triggers_fixture(camera_configs_fixture: CameraConfigs) -> MultiCameraTriggerOrchestrator:
#     return MultiCameraTriggerOrchestrator.from_camera_configs(camera_configs_fixture)
#
#
# @pytest.fixture
# def camera_shared_memory_fixture(image_fixture: np.ndarray,
#                                  camera_configs_fixture: CameraConfigs,
#                                  ) -> Tuple[CameraSharedMemoryManager, CameraSharedMemoryManager]:
#
#     for config in camera_configs_fixture.values():
#         config.resolution = ImageResolution.from_image(image_fixture)
#         config.color_channels = image_fixture.shape[2] if len(image_fixture.shape) == 3 else 1
#         assert config.image_shape == image_fixture.shape
#     lock = multiprocessing.Lock()
#     manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture, lock=lock)
#     assert manager
#     recreated_manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture,
#                                                   lock=lock,
#                                                   existing_shared_memory_names=manager.shared_memory_names
#                                                   )
#     assert recreated_manager.shared_memory_sizes == manager.shared_memory_sizes
#     yield manager, recreated_manager
#
#     manager.close_and_unlink()
#     recreated_manager.close_and_unlink()
#
#
# @pytest.fixture
# def frame_payload_fixture(camera_id_fixture: CameraId,
#                           image_fixture: np.ndarray) -> FramePayload:
#     # Arrange
#     frame = FramePayload.create_initial_frame(camera_id=camera_id_fixture,
#                                               image_shape=image_fixture.shape)
#     frame.image = image_fixture
#     frame.previous_frame_timestamp_ns = time.perf_counter_ns()
#     frame.timestamp_ns = time.perf_counter_ns()
#     frame.success = True
#     # Assert
#     for key, value in frame.model_dump().items():
#         assert value is not None, f"Key {key} is None"
#     assert frame.hydrated
#     assert frame.image_shape == image_fixture.shape
#     assert np.sum(frame.image - image_fixture) == 0
#     return frame
#
#
# @pytest.fixture
# def multi_frame_payload_fixture(camera_ids_fixture: List[CameraId],
#                                 frame_payload_fixture: FramePayload
#                                 ) -> MultiFramePayload:
#     payload = MultiFramePayload.create(camera_ids=camera_ids_fixture,
#                                        multi_frame_number=0)
#
#     for camera_id in camera_ids_fixture:
#         cam_frame = deepcopy(frame_payload_fixture)
#         cam_frame.camera_id = camera_id
#         payload.add_frame(cam_frame)
#     assert payload.full
#     return payload
#
#
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
# @pytest.fixture
# def app_fixture() -> FastAPI:
#     return create_app()
#
#
# @pytest.fixture
# def client_fixture(app_fixture: FastAPI) -> TestClient:
#     with TestClient(app_fixture) as client:
#         yield client
