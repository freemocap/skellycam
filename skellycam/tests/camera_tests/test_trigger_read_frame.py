import threading
from typing import Dict, List
from unittest.mock import Mock

import cv2

from skellycam.core import CameraId
from skellycam.core.camera_group import CameraGroupOrchestrator
from skellycam.core.camera_group.camera.opencv import create_cv2_video_capture
from skellycam.core.camera_group.camera.opencv.get_frame import get_frame
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_1ms


def test_trigger_get_frame_deconstructed(
        camera_group_shared_memory_fixture: tuple[CameraGroupSharedMemory, CameraGroupSharedMemory],
        camera_group_orchestrator_fixture: CameraGroupOrchestrator,
        mock_videocapture: cv2.VideoCapture):
    # init stuff
    shm_parent, shm_child = camera_group_shared_memory_fixture

    assert not camera_group_orchestrator_fixture.cameras_ready

    # check cams ready
    wait_camera_ready_thread = threading.Thread(target=camera_group_orchestrator_fixture.await_for_cameras_ready)
    wait_camera_ready_thread.start()
    for single_camera_triggers in camera_group_orchestrator_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_flag.set()
    wait_camera_ready_thread.join()
    assert camera_group_orchestrator_fixture.cameras_ready

    # Grab a few frames
    number_of_frames_to_test = 4
    for frame_number in range(number_of_frames_to_test):
        # create capture mocks and threads for them to run in
        caps = {
            camera_id: create_cv2_video_capture(config=camera_config)
            for camera_id, camera_config in shm_parent.camera_configs.items()
        }

        for cap in caps.values():
            assert cap.isOpened()
            assert cap.grab_called_count == 0
            assert cap.retrieve_called_count == 0

        frame_read_threads = create_frame_read_threads(
            capture_mocks=caps,
            camera_group_orchestrator_fixture=camera_group_orchestrator_fixture,
            shared_memory_manager=shm_child,
        )
        [thread.start() for thread in frame_read_threads]
        wait_1ms()
        assert all([thread.is_alive() for thread in frame_read_threads])

        # 0
        camera_group_orchestrator_fixture._ensure_cameras_ready()
        wait_1ms()

        for cap in caps.values():
            assert cap.isOpened()
            assert cap.grab_called_count == 0
            assert cap.retrieve_called_count == 0

        # 1
        camera_group_orchestrator_fixture._fire_grab_trigger()
        wait_1ms()

        # 2
        for cap in caps.values():
            assert cap.isOpened()
            assert cap.grab_called_count == 1
            assert cap.retrieve_called_count == 0

        camera_group_orchestrator_fixture._await_frames_grabbed()
        assert camera_group_orchestrator_fixture.frames_grabbed

        # 3
        camera_group_orchestrator_fixture._fire_retrieve_trigger()
        wait_1ms()
        for cap in caps.values():
            assert cap.isOpened()
            assert cap.grab_called_count == 1
            assert cap.retrieve_called_count == 1

        # 4
        camera_group_orchestrator_fixture.await_new_multi_frame_available()
        assert camera_group_orchestrator_fixture.frames_retrieved
        wait_1ms()
        assert camera_group_orchestrator_fixture.new_multi_frame_available

        # 5
        [triggers.set_frame_copied() for triggers in camera_group_orchestrator_fixture.camera_triggers.values()]
        camera_group_orchestrator_fixture._await_mf_copied_from_shm()
        assert not camera_group_orchestrator_fixture.new_multi_frame_available

        # 6
        camera_group_orchestrator_fixture._verify_hunky_dory_after_read()

        [thread.join() for thread in frame_read_threads]


def create_frame_read_threads(
        capture_mocks: Dict[CameraId, Mock],
        camera_group_orchestrator_fixture: CameraGroupOrchestrator,
        shared_memory_manager: CameraGroupSharedMemory,
) -> List[threading.Thread]:
    # create thread for each camera to read mock frames
    frame_read_threads = []
    for camera_id, cap in capture_mocks.items():
        cam_shm = shared_memory_manager.get_camera_shared_memory(camera_id)
        cam_triggers = camera_group_orchestrator_fixture.camera_triggers[camera_id]
        frame_read_threads.append(
            threading.Thread(
                target=get_frame,
                args=(
                    camera_id,
                    cam_shm,
                    cap,
                    cam_triggers,
                    0,
                ),
            )
        )
    return frame_read_threads
