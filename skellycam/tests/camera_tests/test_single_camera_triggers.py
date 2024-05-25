import multiprocessing
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


def test_set_frame_grabbed(single_camera_triggers_fixture:SingleCameraTriggers):
    single_camera_triggers_fixture.set_frame_grabbed()
    assert single_camera_triggers_fixture.frame_grabbed_trigger.is_set()


def test_await_initial_trigger(single_camera_triggers_fixture:SingleCameraTriggers):
    single_camera_triggers_fixture.initial_trigger.set()
    single_camera_triggers_fixture.await_initial_trigger()
    assert not single_camera_triggers_fixture.initial_trigger.is_set()


def test_await_retrieve_trigger(single_camera_triggers_fixture:SingleCameraTriggers):
    single_camera_triggers_fixture.retrieve_frame_trigger.set()
    single_camera_triggers_fixture.await_retrieve_trigger()
    assert single_camera_triggers_fixture.retrieve_frame_trigger.is_set()


def test_await_grab_trigger(single_camera_triggers_fixture:SingleCameraTriggers):
    single_camera_triggers_fixture.grab_frame_trigger.set()
    single_camera_triggers_fixture.await_grab_trigger()
    assert single_camera_triggers_fixture.grab_frame_trigger.is_set()


def test_clear_frame_triggers(single_camera_triggers_fixture:SingleCameraTriggers):
    single_camera_triggers_fixture.grab_frame_trigger.set()
    single_camera_triggers_fixture.frame_grabbed_trigger.set()
    single_camera_triggers_fixture.retrieve_frame_trigger.set()
    single_camera_triggers_fixture.clear_frame_triggers()
    assert not single_camera_triggers_fixture.grab_frame_trigger.is_set()
    assert not single_camera_triggers_fixture.frame_grabbed_trigger.is_set()
    assert not single_camera_triggers_fixture.retrieve_frame_trigger.is_set()
