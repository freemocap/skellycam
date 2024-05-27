import threading
from typing import Dict, List
from unittest.mock import Mock

from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager
from skellycam.tests.mocks import create_cv2_video_capture_mock


def test_trigger_get_frame_deconstructed(camera_shared_memory_fixture: CameraSharedMemoryManager):

    # init stuff
    shm_parent, shm_child = camera_shared_memory_fixture
    camera_configs = shm_parent.camera_configs
    multi_camera_triggers = MultiCameraTriggerOrchestrator.from_camera_configs(camera_configs)

    assert not multi_camera_triggers.cameras_ready

    # check cams ready
    wait_camera_ready_thread = threading.Thread(target=multi_camera_triggers.wait_for_cameras_ready)
    wait_camera_ready_thread.start()
    for single_camera_triggers in multi_camera_triggers.single_camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_camera_ready_thread.join()
    assert multi_camera_triggers.cameras_ready

    # Grab a few frames
    number_of_frames_to_test = 4
    for frame_number in range(number_of_frames_to_test):
        # create capture mocks and threads for them to run in
        caps = {
            camera_id: create_cv2_video_capture_mock(camera_config)
            for camera_id, camera_config in camera_configs.items()
        }

        for cap in caps.values():
            assert cap.isOpened()
            assert not cap.grab.called
            assert not cap.retrieve.called

        frame_read_threads = create_frame_read_threads(
            camera_configs=camera_configs,
            capture_mocks=caps,
            multi_camera_triggers=multi_camera_triggers,
            shared_memory_manager=shm_child,
        )
        [thread.start() for thread in frame_read_threads]
        wait_10ms()
        assert all([thread.is_alive() for thread in frame_read_threads])

        # 0
        multi_camera_triggers._ensure_cameras_ready()
        wait_10ms()

        for cap in caps.values():
            assert cap.isOpened()
            assert not cap.grab.called
            assert not cap.retrieve.called

        # 1
        multi_camera_triggers._fire_grab_trigger()
        wait_10ms()

        # 2
        for cap in caps.values():
            assert cap.isOpened()
            assert cap.grab.called
            assert not cap.retrieve.called

        multi_camera_triggers._await_frames_grabbed()
        assert multi_camera_triggers.frames_grabbed

        # 3
        multi_camera_triggers._fire_retrieve_trigger()
        wait_10ms()
        for cap in caps.values():
            assert cap.isOpened()
            assert cap.grab.called
            assert cap.retrieve.called

        # 4
        multi_camera_triggers.await_new_frames_available()
        assert multi_camera_triggers.frames_retrieved
        wait_10ms()
        assert multi_camera_triggers.new_frames_available

        # 5
        [triggers.set_frame_copied() for triggers in multi_camera_triggers.single_camera_triggers.values()]
        multi_camera_triggers._await_frames_copied()
        assert not multi_camera_triggers.new_frames_available

        # 6
        multi_camera_triggers._verify_hunky_dory_after_read()

        [thread.join() for thread in frame_read_threads]


def create_frame_read_threads(
        camera_configs: "CameraConfigs",
        capture_mocks: Dict["CameraId", Mock],
        multi_camera_triggers: "MultiCameraTriggers",
        shared_memory_manager: "CameraSharedMemoryManager",
) -> List[threading.Thread]:
    from skellycam.core.cameras.trigger_camera.trigger_get_frame import get_frame

    # create thread for each camera to read mock frames
    frame_read_threads = []
    for camera_id, cap in capture_mocks.items():
        cam_shm = shared_memory_manager.get_camera_shared_memory(camera_id)
        cam_triggers = multi_camera_triggers.single_camera_triggers[camera_id]
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
