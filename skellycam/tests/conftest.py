import multiprocessing
import time
from typing import Tuple, List
from unittest.mock import patch

import numpy as np
import pytest
from _pytest.terminal import TerminalReporter
from fastapi import FastAPI
from starlette.testclient import TestClient

from skellycam.api import create_app
from skellycam.app.app_controller.app_controller import AppController, create_app_controller, get_app_controller
from skellycam.core import CameraId
from skellycam.core.camera_group import CameraGroupOrchestrator
from skellycam.core.camera_group.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.core.detection.camera_device_info import AvailableDevices, CameraDeviceInfo, DeviceVideoFormat
from skellycam.core.frames.payloads.frame_payload_dto import FramePayloadDTO
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_DTYPE, FRAME_METADATA_SHAPE
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler
from skellycam.tests.mocks import MockVideoCapture


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


@pytest.fixture(params=[(12, 15, 3),  # landscape
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


@pytest.fixture
def image_resolution_fixture(image_shape_fixture: Tuple[int, int, int]
                             ) -> ImageResolution:
    return ImageResolution(width=image_shape_fixture[0], height=image_shape_fixture[1])


@pytest.fixture
def available_devices_fixture(camera_configs_fixture: CameraConfigs) -> AvailableDevices:
    available_devices = {}
    for camera_id, config in camera_configs_fixture.items():
        d1 = DeviceVideoFormat(width=config.resolution.width,
                               height=config.resolution.height,
                               pixel_format=config.pixel_format,
                               framerate=config.framerate)
        d2 = DeviceVideoFormat(width=config.resolution.width // 2,
                               height=config.resolution.height // 2,
                               pixel_format=config.pixel_format,
                               framerate=config.framerate * 2)
        assert isinstance(d1, DeviceVideoFormat)
        assert isinstance(d2, DeviceVideoFormat)
        device_info = CameraDeviceInfo(device_address=f"device_{camera_id}/video{camera_id}/wheee!",
                                       description=f"Camera {camera_id} - {config.resolution}",
                                       cv2_port=camera_id,
                                       available_video_formats=[d1, d2]
                                       )
        assert isinstance(device_info, CameraDeviceInfo)
        available_devices[camera_id] = device_info

    assert all([isinstance(device, CameraDeviceInfo) for device in available_devices.values()])
    assert len(available_devices) == len(camera_configs_fixture)
    return available_devices


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
def frame_metadata_fixture(request: pytest.fixture,
                           camera_config_fixture: CameraConfig
                           ) -> np.ndarray:
    metadata_array = np.ndarray(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)
    metadata_array[:] = time.perf_counter_ns()
    metadata_array[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_config_fixture.camera_id
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


@pytest.fixture(params=[[0], [0, "2"], [1e3]])
def camera_ids_fixture(request: pytest.fixture) -> List[CameraId]:
    return [CameraId(cam_id) for cam_id in request.param]


@pytest.fixture()
def default_camera_config_fixture() -> CameraConfig:
    return CameraConfig()


@pytest.fixture()
def camera_config_fixture(camera_id_fixture: CameraId,
                          image_shape_fixture: Tuple[int, int, int]) -> CameraConfig:
    resolution = ImageResolution(height=image_shape_fixture[0], width=image_shape_fixture[1])
    return CameraConfig(camera_id=camera_id_fixture, resolution=resolution)


@pytest.fixture()
def camera_configs_fixture(camera_ids_fixture: List[CameraId],
                           image_shape_fixture: Tuple[int, int, int]
                           ) -> CameraConfigs:
    camera_configs = {}
    for cam_id in camera_ids_fixture:
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
def single_camera_triggers_fixture(camera_id_fixture: CameraId,
                                   exit_event_fixture: multiprocessing.Event
                                   ) -> CameraFrameLoopFlags:
    return CameraFrameLoopFlags.create(camera_id=camera_id_fixture, exit_event=exit_event_fixture)


@pytest.fixture
def camera_group_shared_memory_fixture(camera_configs_fixture: CameraConfigs,
                                       ) -> Tuple[CameraGroupSharedMemory, CameraGroupSharedMemory]:
    manager = CameraGroupSharedMemory.create(camera_configs=camera_configs_fixture)
    assert manager
    recreated_manager = CameraGroupSharedMemory.recreate(camera_configs=camera_configs_fixture,
                                                         group_shm_names=manager.shared_memory_names
                                                         )
    yield manager, recreated_manager

    recreated_manager.close()
    manager.close_and_unlink()


def camera_group_orchestrator_fixture(camera_configs_fixture: CameraConfigs,
                                      exit_event_fixture: multiprocessing.Event
                                      ) -> CameraGroupOrchestrator:
    yield CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs_fixture,
                                                      exit_event=exit_event_fixture)


def camera_group_shared_memory_names_fixture(camera_group_shared_memory_fixture: Tuple[
    CameraGroupSharedMemory, CameraGroupSharedMemory]) -> GroupSharedMemoryNames:
    og_manager, recreated_manager = camera_group_shared_memory_fixture
    yield og_manager.shared_memory_names


@pytest.fixture
def exit_event_fixture() -> multiprocessing.Event:
    yield multiprocessing.Event()


@pytest.fixture
def camera_group_shared_memory_names_fixture(camera_group_shared_memory_fixture: Tuple[
    CameraGroupSharedMemory, CameraGroupSharedMemory]) -> GroupSharedMemoryNames:
    og_manager, recreated_manager = camera_group_shared_memory_fixture
    yield og_manager.shared_memory_names


@pytest.fixture
def frame_wrangler_fixture(camera_configs_fixture: CameraConfigs,
                           camera_group_shared_memory_names_fixture: GroupSharedMemoryNames,
                           camera_group_orchestrator_fixture: CameraGroupOrchestrator,
                           exit_event_fixture: multiprocessing.Event) -> FrameWrangler:
    frame_wrangler = FrameWrangler(camera_configs=camera_configs_fixture,
                                   group_shm_names=camera_group_shared_memory_names_fixture,
                                   group_orchestrator=camera_group_orchestrator_fixture,
                                   exit_event=exit_event_fixture)
    assert frame_wrangler
    yield frame_wrangler
    frame_wrangler.close()


@pytest.fixture
def mock_videocapture():
    with patch('cv2.VideoCapture', MockVideoCapture):
        yield


# @pytest.fixture()
# def mock_cv2_video_capture(camera_config: CameraConfig) -> MagicMock:
#     from skellycam.tests.mocks import create_cv2_video_capture_mock
#     mock = create_cv2_video_capture_mock(camera_config=camera_config)
#     assert mock.isOpened()
#     yield mock
#     mock.release()


@pytest.fixture
def app_fixture() -> FastAPI:
    app = create_app()
    assert app
    yield app


@pytest.fixture
def client_fixture(app_fixture: FastAPI) -> TestClient:
    with TestClient(app_fixture) as client:
        yield client
    client.close()


@pytest.fixture
def controller_fixture() -> AppController:
    create_app_controller()
    controller = get_app_controller()
    assert isinstance(controller, AppController)
    yield controller
    controller.close()

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
