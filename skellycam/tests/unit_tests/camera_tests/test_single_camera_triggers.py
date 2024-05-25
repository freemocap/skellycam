import threading
from multiprocessing import synchronize

from skellycam.core import CameraId
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers


def test_from_camera_config(camera_id_fixture: CameraId):
    triggers = SingleCameraTriggers.from_camera_id(camera_id_fixture)
    assert triggers.camera_id == camera_id_fixture
    assert isinstance(triggers.camera_ready_event, synchronize.Event)


def test_set_ready(single_camera_triggers_fixture: SingleCameraTriggers):
    single_camera_triggers_fixture.set_ready()
    assert single_camera_triggers_fixture.camera_ready_event.is_set()


def test_initial_trigger(single_camera_triggers_fixture: SingleCameraTriggers):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_initial_trigger)
    await_thread.start()
    single_camera_triggers_fixture.initial_trigger.set()
    assert single_camera_triggers_fixture.initial_trigger.is_set()
    await_thread.join()
    assert not single_camera_triggers_fixture.initial_trigger.is_set()


def test_frame_grab_trigger(single_camera_triggers_fixture: SingleCameraTriggers):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_grab_trigger)
    await_thread.start()
    single_camera_triggers_fixture.grab_frame_trigger.set()
    assert single_camera_triggers_fixture.grab_frame_trigger.is_set()
    await_thread.join()
    single_camera_triggers_fixture.set_frame_grabbed()
    assert not single_camera_triggers_fixture.grab_frame_trigger.is_set()


def test_frame_retrieve_trigger(single_camera_triggers_fixture: SingleCameraTriggers):
    await_thread = threading.Thread(target=single_camera_triggers_fixture.await_retrieve_trigger)
    await_thread.start()
    single_camera_triggers_fixture.retrieve_frame_trigger.set()
    assert single_camera_triggers_fixture.retrieve_frame_trigger.is_set()
    await_thread.join()
    single_camera_triggers_fixture.set_frame_retrieved()
    assert not single_camera_triggers_fixture.retrieve_frame_trigger.is_set()
