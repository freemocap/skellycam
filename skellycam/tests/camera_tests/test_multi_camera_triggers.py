import multiprocessing
import threading

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group import CameraGroupOrchestrator
from skellycam.utilities.wait_functions import wait_1ms


def test_multi_camera_triggers_from_camera_configs(camera_configs_fixture: CameraConfigs,
                                                   exit_event_fixture=multiprocessing.Event()):
    camera_group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs_fixture,
                                                                            exit_event=exit_event_fixture)
    assert len(camera_group_orchestrator.camera_triggers) == len(camera_configs_fixture)


def test_multi_camera_triggers_exit_event(camera_configs_fixture: CameraConfigs,
                                          exit_event_fixture: multiprocessing.Event):
    camera_group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs_fixture,
                                                                            exit_event=exit_event_fixture)

    assert camera_group_orchestrator.should_continue is True
    wait_threads = [threading.Thread(target=camera_group_orchestrator.await_new_frames_available),
                    threading.Thread(target=camera_group_orchestrator.await_for_cameras_ready),
                    threading.Thread(target=camera_group_orchestrator._await_frames_grabbed),
                    threading.Thread(target=camera_group_orchestrator._wait_for_frames_grabbed_triggers_reset),
                    threading.Thread(target=camera_group_orchestrator._wait_for_retrieve_triggers_reset),
                    threading.Thread(target=camera_group_orchestrator._await_multiframe_pulled_from_shm),
                    threading.Thread(target=camera_group_orchestrator.fire_initial_triggers)]
    [thread.start() for thread in wait_threads]
    wait_1ms()
    thread_statuses = [thread.is_alive() for thread in wait_threads]
    assert any(
        thread_statuses)  # TODO - get specific enough with the set up that we can assert that ALL threads are alive
    exit_event_fixture.set()
    assert camera_group_orchestrator.should_continue is False
    [thread.join() for thread in wait_threads]


def test_multi_camera_triggers_cameras_ready(camera_group_orchestrator_fixture: CameraGroupOrchestrator):
    assert not camera_group_orchestrator_fixture.cameras_ready
    for single_camera_triggers in camera_group_orchestrator_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    assert camera_group_orchestrator_fixture.cameras_ready


def test_multi_camera_triggers_wait_for_cameras_ready(camera_group_orchestrator_fixture: CameraGroupOrchestrator):
    wait_thread = threading.Thread(target=camera_group_orchestrator_fixture.await_for_cameras_ready)
    wait_thread.start()
    for single_camera_triggers in camera_group_orchestrator_fixture.camera_triggers.values():
        single_camera_triggers.camera_ready_event.set()
    wait_thread.join()
    assert camera_group_orchestrator_fixture.cameras_ready
