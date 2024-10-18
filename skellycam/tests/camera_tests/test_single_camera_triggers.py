import multiprocessing
import threading
from multiprocessing import synchronize

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.utilities.wait_functions import wait_1ms


def test_from_camera_config(camera_id_fixture: CameraId,
                            exit_event_fixture: multiprocessing.Event):
    triggers = CameraFrameLoopFlags.create(camera_id=camera_id_fixture, exit_event=exit_event_fixture)
    assert triggers.camera_id == camera_id_fixture
    assert isinstance(triggers.camera_ready_flag, synchronize.Event)


def test_set_ready(single_camera_triggers_fixture: CameraFrameLoopFlags):
    single_camera_triggers_fixture.set_camera_ready()
    assert single_camera_triggers_fixture.camera_ready_flag.is_set()


def test_initial_trigger(single_camera_triggers_fixture: CameraFrameLoopFlags):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_frame_loop_initialization)
    await_thread.start()
    single_camera_triggers_fixture.frame_read_initialization_flag.set()
    assert single_camera_triggers_fixture.frame_read_initialization_flag.is_set()
    await_thread.join()
    assert not single_camera_triggers_fixture.frame_read_initialization_flag.is_set()


def test_frame_grab_trigger(single_camera_triggers_fixture: CameraFrameLoopFlags):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_should_grab)
    await_thread.start()
    single_camera_triggers_fixture.should_grab_frame_flag.set()
    assert single_camera_triggers_fixture.should_grab_frame_flag.is_set()
    await_thread.join()
    single_camera_triggers_fixture.set_frame_grabbed()
    assert not single_camera_triggers_fixture.should_grab_frame_flag.is_set()


def test_frame_retrieve_trigger(single_camera_triggers_fixture: CameraFrameLoopFlags):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_should_retrieve)
    await_thread.start()
    single_camera_triggers_fixture.should_retrieve_frame_flag.set()
    assert single_camera_triggers_fixture.should_retrieve_frame_flag.is_set()
    await_thread.join()
    single_camera_triggers_fixture.set_new_frame_available()
    assert not single_camera_triggers_fixture.should_retrieve_frame_flag.is_set()


def test_camera_triggers_exit_event(camera_id_fixture: CameraId,
                                    exit_event_fixture: multiprocessing.Event):
    camera_triggers = CameraFrameLoopFlags.create(camera_id=camera_id_fixture,
                                                  exit_event=exit_event_fixture)
    assert camera_triggers.should_continue is True
    wait_threads = [threading.Thread(target=camera_triggers.await_frame_loop_initialization),
                    threading.Thread(target=camera_triggers.await_should_grab),
                    threading.Thread(target=camera_triggers.await_should_retrieve),
                    ]
    [thread.start() for thread in wait_threads]
    wait_1ms()
    assert any([thread.is_alive() for thread in wait_threads])
    exit_event_fixture.set()
    assert camera_triggers.should_continue is False
    [thread.join() for thread in wait_threads]
