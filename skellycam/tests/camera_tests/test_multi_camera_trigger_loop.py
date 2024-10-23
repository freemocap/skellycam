import multiprocessing
import threading

import cv2
import pytest
from skellycam.core.camera_group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory_manager import CameraGroupSharedMemory

from skellycam.core.camera_group import CameraGroupOrchestrator
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.utilities.wait_functions import wait_10ms


@pytest.mark.skip(
    reason="Realized I don't need to mock the whole videocapture, just the outer method that this loop calls - need implement that before re-activating this test.")
def test_multi_camera_trigger_loop(
        camera_configs_fixture: CameraConfigs,
        camera_group_shared_memory_fixture: CameraGroupSharedMemory,
        mock_videocapture: cv2.VideoCapture
):
    shm_manager, recreated_shm_manager = camera_group_shared_memory_fixture
    shm_names = shm_manager.shared_memory_names
    exit_event = multiprocessing.Event()
    camera_group_orchestrator = CameraGroupOrchestrator.from_camera_configs(shm_manager.connected_camera_configs)
    [camera_group_orchestrator.frame_loop_flags[camera_id].camera_ready_flag.set() for camera_id in
     camera_configs_fixture.keys()]
    loop_thread = threading.Thread(
        target=camera_group_trigger_loop, args=(camera_configs_fixture,
                                                camera_group_orchestrator,
                                                shm_names,
                                                exit_event,
                                                3,
                                                )
    )
    loop_thread.start()
    wait_10ms()
    exit_event.set()
    loop_thread.join()
    assert True
