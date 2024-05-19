import threading

import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggers


def test_multi_camera_triggers_from_camera_configs(camera_configs_fixture: CameraConfigs):
    multi_camera_triggers = MultiCameraTriggers.from_camera_configs(camera_configs_fixture)
    assert len(multi_camera_triggers.single_camera_triggers) == len(camera_configs_fixture)

def test_multi_camera_triggers_cameras_ready(multi_camera_triggers_fixture: MultiCameraTriggers):
    assert not multi_camera_triggers_fixture.cameras_ready_triggers_set
    for single_camera_triggers in multi_camera_triggers_fixture.single_camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    assert multi_camera_triggers_fixture.cameras_ready_triggers_set

def test_multi_camera_triggers_wait_for_cameras_ready(multi_camera_triggers_fixture: MultiCameraTriggers):
    wait_thread = threading.Thread(target=multi_camera_triggers_fixture.wait_for_cameras_ready)
    wait_thread.start()
    for single_camera_triggers in multi_camera_triggers_fixture.single_camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_thread.join()
    assert multi_camera_triggers_fixture.cameras_ready_triggers_set
