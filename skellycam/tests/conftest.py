# import enum
# import multiprocessing
# import os
# import time
# from copy import deepcopy
# from typing import List, Tuple
#
# import numpy as np
# import pytest
# from fastapi import FastAPI
# from starlette.testclient import TestClient
#
# from skellycam.api.app_factory import create_app
# from skellycam.core import CameraId
# from skellycam.core.cameras.config.camera_config import CameraConfig
# from skellycam.core.cameras.config.camera_configs import CameraConfigs
# from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
# from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
# from skellycam.core.detection.image_resolution import ImageResolution
# from skellycam.core.frames.frame_payload import FramePayload
# from skellycam.core.frames.frontend_image_payload import FrontendImagePayload
# from skellycam.core.frames.multi_frame_payload import MultiFramePayload
# from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager
#
# TEST_ENV_NAME = 'TEST_ENV'
#
#
# def pytest_terminal_summary(terminalreporter):
#     """
#     This hook is called after the whole test run finishes,
#     you can use it to add a summary to the terminal output.
#     """
#     for report in terminalreporter.getreports("failed"):
#         if report.location:
#             file_path, line_num, _ = report.location
#             terminalreporter.write_line(f"FAILED {file_path}:{line_num} - {report.longrepr}")
#         else:
#             terminalreporter.write_line(f"FAILED {report.longrepr}")
#
#
#
#
# @pytest.fixture(scope='session', autouse=True)
# def set_test_env_variable():
#     # Set the environment variable before any tests run
#     #TODO - make a better way to set the runtime environment - we'll want `testing` (running tests), `development`(running from source), and `production` (running from a built package, i.e. from pypi or a wheel file)
#     os.environ[TEST_ENV_NAME] = 'true'
#     yield
#     # Clean up the environment variable after all tests have run
#     del os.environ[TEST_ENV_NAME]
#
#
# class TestFullSizeImageShapes(enum.Enum):
#     RGB_LANDSCAPE = (480, 640, 3)
#     RGB_PORTRAIT = (640, 480, 3)
#     SQUARE_RGB = (640, 640, 3)
#     RGB_720P = (720, 1280, 3)
#     RGB_1080P = (1080, 1920, 3)
#     RGB_4K = (2160, 3840, 3)
#     # TODO - Support monochrome images
#     # MONO_2 = (480, 640)
#     # MONO_3 = (480, 640, 1)
#     # SQUARE_MONO = (640, 640)
#
#
# class WeeImageShapes(enum.Enum):
#     LANDSCAPE = (48, 64, 3)
#     PORTRAIT = (64, 48, 3)
#     SQUARE = (64, 64, 3)
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
# test_camera_ids = [1, "2", 4, ]
#
#
# @pytest.fixture(params=test_camera_ids)
# def camera_id_fixture(request) -> "CameraId":
#     from skellycam.core import CameraId
#     return CameraId(request.param)
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
# @pytest.fixture
# def camera_config_fixture(camera_ids_fixture: List[CameraId]) -> CameraConfig:
#     return CameraConfig(camera_id=camera_ids_fixture[0])
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
