import threading

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group import CameraGroupOrchestrator


def test_multi_camera_triggers_from_camera_configs(camera_configs_fixture: CameraConfigs):
    multi_camera_triggers = CameraGroupOrchestrator.from_camera_configs(camera_configs_fixture)
    assert len(multi_camera_triggers.camera_triggers) == len(camera_configs_fixture)


def test_multi_camera_triggers_cameras_ready(multi_camera_triggers_fixture: CameraGroupOrchestrator):
    assert not multi_camera_triggers_fixture.cameras_ready
    for single_camera_triggers in multi_camera_triggers_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    assert multi_camera_triggers_fixture.cameras_ready


def test_multi_camera_triggers_wait_for_cameras_ready(multi_camera_triggers_fixture: CameraGroupOrchestrator):
    wait_thread = threading.Thread(target=multi_camera_triggers_fixture.wait_for_cameras_ready)
    wait_thread.start()
    for single_camera_triggers in multi_camera_triggers_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_thread.join()
    assert multi_camera_triggers_fixture.cameras_ready
