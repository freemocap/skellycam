"""CPU fakes prove event-loop boundaries without opening camera hardware."""

import asyncio
import multiprocessing
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from skellycam.core.camera.camera_manager import CameraManager
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory


@pytest.fixture
def group(monkeypatch):
    ipc = Mock(spec=CameraGroupIPC)
    ipc.group_id = "camera-startup"
    ipc.should_continue = True
    ipc.timebase_mapping = Mock()
    ipc.pubsub = Mock()
    cameras = Mock(spec=CameraManager)
    cameras.orchestrator = SimpleNamespace(camera_statuses={})
    config = CameraConfig(camera_id="camera", camera_index=0)
    group = CameraGroup(ipc=ipc, cameras=cameras, configs={config.camera_id: config})
    monkeypatch.setattr("skellycam.core.camera_group.camera_group.logger", Mock())
    monkeypatch.setattr("skellycam.core.camera_group.camera_group_manager.logger", Mock())
    return group


@pytest.mark.parametrize("stage", ["spawn", "shm", "publish"])
async def test_blocking_startup_steps_run_off_loop_and_cancel_after_completion(group, stage):
    entered, release = Event(), Event()
    worker_ids = []
    shm = Mock(spec=CameraGroupSharedMemory)

    def gate(*args, **kwargs):
        worker_ids.append(get_ident())
        entered.set()
        assert release.wait(3)
        return shm

    if stage == "spawn":
        group.cameras.start.side_effect = gate
    elif stage == "publish":
        group.ipc.publish_shm_message.side_effect = gate
    with patch("skellycam.core.camera_group.camera_group.await_extracted_configs",
               new=AsyncMock(return_value=group.configs)), patch.object(
        CameraGroupSharedMemory, "create", side_effect=gate if stage == "shm" else None, return_value=shm,
    ) as allocate:
        task = asyncio.create_task(group.start())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
            assert worker_ids[0] != get_ident()
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            group.cameras.close.assert_not_called()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    group.cameras.close.assert_called_once()
    assert not group.started and not group.ipc.should_continue
    if stage == "spawn":
        allocate.assert_not_called()
    else:
        shm.unlink_and_close.assert_called_once()


async def test_success_publishes_same_config_and_shared_memory(group):
    shm = Mock(spec=CameraGroupSharedMemory)
    with patch("skellycam.core.camera_group.camera_group.await_extracted_configs",
               new=AsyncMock(return_value=group.configs)), patch.object(CameraGroupSharedMemory, "create", return_value=shm):
        assert await group.start() == group.configs
    assert group.shm is shm
    group.ipc.publish_shm_message.assert_called_once_with(shm_dto=shm.to_dto.return_value)
    await group.close()
    await group.close()
    group.cameras.close.assert_called_once()
    shm.unlink_and_close.assert_called_once()


async def test_close_waits_for_owned_native_cleanup_through_cancellation(group):
    entered, release = Event(), Event()
    group.shm = Mock(spec=CameraGroupSharedMemory)

    def close():
        entered.set()
        assert release.wait(3)

    group.cameras.close.side_effect = close
    task = asyncio.create_task(group.close())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        group.shm.unlink_and_close.assert_not_called()
        second_close = asyncio.create_task(group.close())
        await asyncio.sleep(0)
        assert not second_close.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await second_close
    group.shm.unlink_and_close.assert_called_once()
    await group.close()
    group.cameras.close.assert_called_once()


def manager():
    registry = Mock(spec=WorkerRegistry)
    registry.heartbeat_timestamp = multiprocessing.Value("d", 0.0)
    return CameraGroupManager(global_kill_flag=multiprocessing.Value("b", False), worker_registry=registry)


async def test_manager_creation_is_off_loop_and_cancelled_resources_remain_owned_until_closed(group):
    owner = manager()
    entered, release = Event(), Event()
    create_ids = []

    def create(**kwargs):
        create_ids.append(get_ident())
        entered.set()
        assert release.wait(3)
        return group

    with patch.object(CameraGroup, "create", side_effect=create):
        task = asyncio.create_task(owner.create_and_start_camera_group(group.configs))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            assert create_ids[0] != get_ident()
            group.cameras.start.assert_not_called()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    group.cameras.close.assert_called_once()
    assert owner.camera_groups == {}


async def test_start_failure_keeps_failed_cleanup_registered_for_retry(group):
    owner = manager()
    group.cameras.start.side_effect = RuntimeError("start failed")
    group.cameras.close.side_effect = RuntimeError("worker is still running")
    with patch.object(CameraGroup, "create", return_value=group):
        with pytest.raises(RuntimeError, match="still running"):
            await owner.create_and_start_camera_group(group.configs)
    assert owner.camera_groups[group.id] is group
    group.cameras.close.side_effect = None
    await owner.close_all_camera_groups()
    assert owner.camera_groups == {}


async def test_configuration_failure_cleans_started_workers(group):
    owner = manager()
    with patch.object(CameraGroup, "create", return_value=group), patch(
        "skellycam.core.camera_group.camera_group.await_extracted_configs",
        new=AsyncMock(side_effect=RuntimeError("camera configuration timed out")),
    ):
        with pytest.raises(RuntimeError, match="configuration timed out"):
            await owner.create_and_start_camera_group(group.configs)
    group.cameras.close.assert_called_once()
    assert owner.camera_groups == {} and owner.camera_group_framerate_subscriptions == {}
