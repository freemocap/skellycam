import threading
import time

from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggers
from skellycam.core.cameras.trigger_camera.trigger_get_frame import get_frame
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager
from skellycam.tests.mocks import create_cv2_video_capture_mock


def test_trigger_read_frame(camera_shared_memory_fixture: CameraSharedMemoryManager):
    shm_parent, shm_child = camera_shared_memory_fixture
    camera_configs = shm_parent.camera_configs
    multi_camera_triggers = MultiCameraTriggers.from_camera_configs(camera_configs)
    caps = {camera_id: create_cv2_video_capture_mock(camera_config)
            for camera_id, camera_config in camera_configs.items()}

    assert not multi_camera_triggers.cameras_ready
    assert all([caps.isOpened() for caps in caps.values()])
    wait_camera_ready_thread = threading.Thread(target=multi_camera_triggers.wait_for_cameras_ready)
    wait_camera_ready_thread.start()
    for single_camera_triggers in multi_camera_triggers.single_camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_camera_ready_thread.join()
    assert multi_camera_triggers.cameras_ready

    frame_read_threads = []
    for camera_id, cap in caps.items():
        frame = FramePayload.create_initial_frame(camera_id=camera_id,
                                                  image_shape=camera_configs[camera_id].image_shape,
                                                  frame_number=0)
        cam_shm = shm_child.get_camera_shared_memory(camera_id)
        cam_triggers = multi_camera_triggers.single_camera_triggers[camera_id]
        frame_read_threads.append(threading.Thread(target=get_frame, args=(camera_id,
                                                                           cam_shm,
                                                                           cap,
                                                                           frame,
                                                                           cam_triggers,
                                                                           )
                                                   )
                                  )
    [thread.start() for thread in frame_read_threads]

    for cap in caps.values():
        assert cap.isOpened()
        assert not cap.grab.called
        assert not cap.retrieve.called

    multi_camera_triggers._fire_grab_trigger()
    time.sleep(0.1)
    for cap in caps.values():
        assert cap.isOpened()
        assert cap.grab.called
        assert not cap.retrieve.called

    multi_camera_triggers._await_frame_grabbed_trigger_set()

    multi_camera_triggers._fire_retrieve_trigger()
    time.sleep(0.1)
    for cap in caps.values():
        assert cap.isOpened()
        assert cap.grab.called
        assert cap.retrieve.called

    [thread.join() for thread in frame_read_threads]
