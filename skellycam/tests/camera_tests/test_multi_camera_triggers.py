import threading

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator


def test_multi_camera_triggers_from_camera_configs(camera_configs_fixture: CameraConfigs):
    multi_camera_triggers = CameraGroupOrchestrator.from_camera_configs(camera_configs_fixture)
    assert len(multi_camera_triggers.camera_triggers) == len(camera_configs_fixture)


def test_multi_camera_triggers_cameras_ready(camera_group_orchestrator_fixture: CameraGroupOrchestrator):
    assert not camera_group_orchestrator_fixture.cameras_ready
    for single_camera_triggers in camera_group_orchestrator_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    assert camera_group_orchestrator_fixture.cameras_ready


def test_multi_camera_triggers_wait_for_cameras_ready(camera_group_orchestrator_fixture: CameraGroupOrchestrator):
    wait_thread = threading.Thread(target=camera_group_orchestrator_fixture.wait_for_cameras_ready)
    wait_thread.start()
    for single_camera_triggers in camera_group_orchestrator_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_thread.join()
    assert camera_group_orchestrator_fixture.cameras_ready
