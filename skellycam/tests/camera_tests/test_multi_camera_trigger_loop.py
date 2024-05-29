import multiprocessing
import threading

import cv2
import pytest

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
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
    camera_group_orchestrator = CameraGroupOrchestrator.from_camera_configs(shm_manager.camera_configs)
    [camera_group_orchestrator.camera_triggers[camera_id].camera_ready_event.set() for camera_id in
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
