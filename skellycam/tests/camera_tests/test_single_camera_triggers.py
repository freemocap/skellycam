import multiprocessing
import threading
from multiprocessing import synchronize

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_triggers import CameraTriggers
from skellycam.utilities.wait_functions import wait_1ms


def test_from_camera_config(camera_id_fixture: CameraId,
                            exit_event_fixture: multiprocessing.Event):
    triggers = CameraTriggers.from_camera_id(camera_id=camera_id_fixture, exit_event=exit_event_fixture)
    assert triggers.camera_id == camera_id_fixture
    assert isinstance(triggers.camera_ready_event, synchronize.Event)


def test_set_ready(single_camera_triggers_fixture: CameraTriggers):
    single_camera_triggers_fixture.set_ready()
    assert single_camera_triggers_fixture.camera_ready_event.is_set()


def test_initial_trigger(single_camera_triggers_fixture: CameraTriggers):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_initial_trigger)
    await_thread.start()
    single_camera_triggers_fixture.initial_trigger.set()
    assert single_camera_triggers_fixture.initial_trigger.is_set()
    await_thread.join()
    assert not single_camera_triggers_fixture.initial_trigger.is_set()


def test_frame_grab_trigger(single_camera_triggers_fixture: CameraTriggers):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_grab_trigger)
    await_thread.start()
    single_camera_triggers_fixture.grab_frame_trigger.set()
    assert single_camera_triggers_fixture.grab_frame_trigger.is_set()
    await_thread.join()
    single_camera_triggers_fixture.set_frame_grabbed()
    assert not single_camera_triggers_fixture.grab_frame_trigger.is_set()


def test_frame_retrieve_trigger(single_camera_triggers_fixture: CameraTriggers):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_retrieve_trigger)
    await_thread.start()
    single_camera_triggers_fixture.retrieve_frame_trigger.set()
    assert single_camera_triggers_fixture.retrieve_frame_trigger.is_set()
    await_thread.join()
    single_camera_triggers_fixture.set_new_frame_available()
    assert not single_camera_triggers_fixture.retrieve_frame_trigger.is_set()


def test_camera_triggers_exit_event(camera_id_fixture: CameraId,
                                    exit_event_fixture: multiprocessing.Event):
    camera_triggers = CameraTriggers.from_camera_id(camera_id=camera_id_fixture,
                                                    exit_event=exit_event_fixture)
    assert camera_triggers.should_continue is True
    wait_threads = [threading.Thread(target=camera_triggers.await_initial_trigger),
                    threading.Thread(target=camera_triggers.await_grab_trigger),
                    threading.Thread(target=camera_triggers.await_retrieve_trigger),
                    ]
    [thread.start() for thread in wait_threads]
    wait_1ms()
    assert any([thread.is_alive() for thread in wait_threads])
    exit_event_fixture.set()
    assert camera_triggers.should_continue is False
    [thread.join() for thread in wait_threads]
