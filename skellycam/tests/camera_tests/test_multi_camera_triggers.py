import threading

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator


def test_multi_camera_triggers_from_camera_configs(camera_configs_fixture: CameraConfigs):
    multi_camera_triggers = MultiCameraTriggerOrchestrator.from_camera_configs(camera_configs_fixture)
    assert len(multi_camera_triggers.single_camera_triggers) == len(camera_configs_fixture)


def test_multi_camera_triggers_cameras_ready(multi_camera_triggers_fixture: MultiCameraTriggerOrchestrator):
    assert not multi_camera_triggers_fixture.cameras_ready
    for single_camera_triggers in multi_camera_triggers_fixture.single_camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    assert multi_camera_triggers_fixture.cameras_ready


def test_multi_camera_triggers_wait_for_cameras_ready(multi_camera_triggers_fixture: MultiCameraTriggerOrchestrator):
    wait_thread = threading.Thread(target=multi_camera_triggers_fixture.wait_for_cameras_ready)
    wait_thread.start()
    for single_camera_triggers in multi_camera_triggers_fixture.single_camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_thread.join()
    assert multi_camera_triggers_fixture.cameras_ready
