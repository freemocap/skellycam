"""Camera shutdown must not depend on acknowledgements from dead workers."""

import asyncio
import logging
import multiprocessing
import time
from unittest.mock import Mock, call

import pytest

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
import skellycam.core.camera_group.camera_orchestrator as orchestrator_module
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.types.type_overloads import TopicSubscriptionQueue


@pytest.fixture
def manager(monkeypatch):
    # Register the app's logging vocabulary without creating log files/handlers.
    for name in ("trace", "success"):
        monkeypatch.setattr(logging.Logger, name, logging.Logger.debug, raising=False)
    queue = Mock(spec=TopicSubscriptionQueue)
    ipc = CameraGroupIPC(
        group_id="shutdown-test",
        pubsub=Mock(spec=PubSubTopicManager),
        extracted_config_subscription=queue,
        recording_finished_subscription=queue,
        global_kill_flag=multiprocessing.Value("b", False),
        heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()),
    )
    statuses = {name: CameraStatus() for name in ("camera1", "camera2")}
    for status in statuses.values():
        status.connected.value = True
    return CameraManager(
        ipc=ipc,
        orchestrator=CameraOrchestrator.from_statuses(statuses),
        camera_workers={},
    )


@pytest.mark.parametrize("paused", [True, False], ids=["pause", "resume"])
@pytest.mark.parametrize("failure", ["error", "closed"])
async def test_state_change_aborts_on_camera_failure(manager, monkeypatch, paused, failure):
    for status in manager.orchestrator.camera_statuses.values():
        status.is_paused.value = not paused

    async def camera_dies_during_wait():
        getattr(manager.orchestrator.camera_statuses["camera2"], failure).value = True
        await asyncio.sleep(0)

    monkeypatch.setattr(orchestrator_module, "await_10ms", camera_dies_during_wait)
    action = manager.pause(True) if paused else manager.unpause(True)
    with pytest.raises(RuntimeError, match="cameras failed or closed.*camera2"):
        await asyncio.wait_for(action, timeout=1)
    assert manager.ipc.shutdown_camera_group_flag.value
    assert not manager.ipc.global_kill_flag.value
    assert all(s.should_close.value for s in manager.orchestrator.camera_statuses.values())


@pytest.mark.parametrize("paused", [True, False], ids=["pause", "resume"])
async def test_state_change_timeout_stops_group(manager, monkeypatch, paused):
    for status in manager.orchestrator.camera_statuses.values():
        status.is_paused.value = not paused
    monkeypatch.setattr(orchestrator_module, "CAMERA_STATE_TIMEOUT_SECONDS", 0.0)
    action = manager.pause(True) if paused else manager.unpause(True)
    with pytest.raises(TimeoutError, match="Timed out waiting for cameras"):
        await asyncio.wait_for(action, timeout=1)
    assert manager.ipc.shutdown_camera_group_flag.value
    assert not manager.ipc.global_kill_flag.value


@pytest.mark.parametrize("paused", [True, False], ids=["pause", "resume"])
async def test_state_change_completes_when_cameras_acknowledge(manager, monkeypatch, paused):
    for status in manager.orchestrator.camera_statuses.values():
        status.is_paused.value = not paused

    async def acknowledge():
        for status in manager.orchestrator.camera_statuses.values():
            status.is_paused.value = bool(status.should_pause.value)

    monkeypatch.setattr(orchestrator_module, "await_10ms", acknowledge)
    action = manager.pause(True) if paused else manager.unpause(True)
    await asyncio.wait_for(action, timeout=1)
    assert manager.ipc.should_continue
    assert all(bool(s.is_paused.value) == paused for s in manager.orchestrator.camera_statuses.values())


@pytest.mark.parametrize("outcome", ["already-dead", "kill-needed", "unkillable", "not-started"])
def test_close_reaches_worker_shutdown_despite_stale_status(manager, monkeypatch, outcome):
    def forbidden_status_wait():
        pytest.fail("Shutdown waited for a dead camera to acknowledge closure")

    # Fail promptly if the old unbounded status wait is reintroduced.
    monkeypatch.setattr(orchestrator_module, "wait_100ms", forbidden_status_wait, raising=False)
    worker = Mock(spec=ManagedWorker)
    worker.pid = None if outcome == "not-started" else 123
    worker.is_alive.return_value = outcome in ("kill-needed", "unkillable")
    if outcome == "kill-needed":
        def killed():
            worker.is_alive.return_value = False
        worker.kill.side_effect = killed
    manager.camera_workers["camera1"] = CameraWorker(
        camera_id="camera1", worker=worker, ipc=manager.ipc,
        orchestrator=manager.orchestrator,
    )
    # Deliberately leave closed=False: an abrupt exit cannot update it.
    if outcome == "unkillable":
        with pytest.raises(RuntimeError, match="could not be killed"):
            manager.close()
        assert manager.camera_workers
    else:
        manager.close()
        assert not manager.camera_workers
        assert all(s.closed.value for s in manager.orchestrator.camera_statuses.values())
        group = CameraGroup(ipc=manager.ipc, configs={}, cameras=manager)
        assert not group.alive
        assert not group.to_state().alive
    assert manager.ipc.shutdown_camera_group_flag.value
    worker.mark_stopping.assert_called_once()
    if outcome in ("kill-needed", "unkillable"):
        worker.terminate.assert_called_once()
        worker.kill.assert_called_once()
        assert worker.join.call_args_list == [call(timeout=3.0), call(timeout=3.0), call(timeout=2.0)]
    else:
        worker.terminate.assert_not_called()
        worker.kill.assert_not_called()
        assert worker.join.call_count == int(outcome == "already-dead")


async def test_group_close_after_recording_failure_releases_shared_memory(manager):
    manager.ipc.should_continue = False
    status = manager.orchestrator.camera_statuses["camera1"]
    status.recording_in_progress.value = True
    status.signal_error()
    shm = Mock(spec=CameraGroupSharedMemory)
    group = CameraGroup(ipc=manager.ipc, configs={}, cameras=manager, shm=shm)
    await asyncio.wait_for(group.close(), timeout=1)
    shm.unlink_and_close.assert_called_once()
    assert status.error.value
    assert not manager.ipc.global_kill_flag.value


@pytest.mark.parametrize("paused", [False, True])
def test_stopped_group_is_not_reported_alive_with_lingering_workers(manager, paused):
    worker = Mock(spec=CameraWorker)
    worker.is_alive.return_value = True
    worker.to_state.return_value = {
        "pid": 123, "name": "lingering-camera", "alive": True, "status": {},
    }
    manager.camera_workers["camera1"] = worker
    for status in manager.orchestrator.camera_statuses.values():
        status.should_pause.value = paused
        status.is_paused.value = paused
    group = CameraGroup(ipc=manager.ipc, configs={}, cameras=manager)
    assert group.alive
    assert group.to_state().alive
    manager.ipc.should_continue = False
    assert not group.alive
    assert not group.to_state().alive
