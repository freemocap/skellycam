"""Regressions reproduced by Core's physical-camera API harness."""
import multiprocessing
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry


def test_unchanged_camera_frame_is_not_copied_or_encoded(monkeypatch):
    group = SimpleNamespace(cameras=SimpleNamespace(all_ready=True),
                            shm=SimpleNamespace(valid=True, latest_multiframe_number=10), get_latest_frames=Mock())
    encode = Mock(return_value=(10, 1.0, memoryview(b'old')))
    monkeypatch.setattr('skellycam.core.camera_group.camera_group.create_frontend_payload', encode)
    assert CameraGroup.get_latest_frontend_payload(group, if_newer_than=10) is None
    group.get_latest_frames.assert_not_called()
    encode.assert_not_called()


def test_snapshot_frame_identity_is_checked_before_encoding(monkeypatch):
    frame = SimpleNamespace(frame_metadata=SimpleNamespace(frame_number=np.array([10])))
    group = SimpleNamespace(cameras=SimpleNamespace(all_ready=True),
                            shm=SimpleNamespace(valid=True, latest_multiframe_number=11), get_latest_frames=Mock(return_value={'A': frame}))
    encode = Mock(return_value=(10, 1.0, memoryview(b'old')))
    monkeypatch.setattr('skellycam.core.camera_group.camera_group.create_frontend_payload', encode)
    assert CameraGroup.get_latest_frontend_payload(group, if_newer_than=10) is None
    encode.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('change_kind', ['add', 'remove', 'resize'])
async def test_camera_membership_and_image_layout_rebuild_shared_memory(change_kind):
    original = {'A': CameraConfig(camera_id='A', camera_index=0)}
    if change_kind == 'remove':
        original['B'] = CameraConfig(camera_id='B', camera_index=1)
    requested = {key: config.model_copy(deep=True) for key, config in original.items()}
    if change_kind == 'add':
        requested['B'] = CameraConfig(camera_id='B', camera_index=1)
    elif change_kind == 'remove':
        requested['B'].use_this_camera = False
    else:
        requested['A'].resolution.width = original['A'].resolution.width + 100
    old_group = Mock(spec=CameraGroup, id='old', camera_ids=list(original), configs=original,
        recording_in_progress=False,
        cameras=SimpleNamespace(orchestrator=SimpleNamespace(any_cameras_recording=False, all_cameras_recording=False)),
        close=AsyncMock(), update_camera_settings=AsyncMock())
    manager = CameraGroupManager(multiprocessing.Value('b', False), Mock(spec=WorkerRegistry))
    manager.camera_groups['old'] = old_group
    manager.camera_group_framerate_subscriptions['old'] = Mock()
    replacement = Mock(spec=CameraGroup)
    manager.create_and_start_camera_group = AsyncMock(return_value=replacement)
    assert await manager.create_or_update_camera_group(requested) is replacement
    old_group.close.assert_awaited_once()
    assert 'old' not in manager.camera_groups
    assert 'old' not in manager.camera_group_framerate_subscriptions
    expected = {key: value for key, value in requested.items() if value.use_this_camera}
    manager.create_and_start_camera_group.assert_awaited_once_with(expected)


@pytest.mark.asyncio
async def test_closing_empty_python_manager_does_not_disable_future_streaming():
    manager = CameraGroupManager(multiprocessing.Value('b', False), Mock(spec=WorkerRegistry))
    await manager.close_all_camera_groups()
    assert not manager.closing


@pytest.mark.asyncio
async def test_rust_disabled_camera_is_removed_from_native_configuration():
    native = Mock()
    configs = {'A': CameraConfig(camera_id='A', camera_index=0),
               'B': CameraConfig(camera_id='B', camera_index=1, use_this_camera=False)}
    group = RustCameraGroup('test-group', configs, native)
    await group.update_camera_settings(configs)
    assert set(native.apply_configs.call_args.args[1]) == {'A'}
    assert set(group.configs) == {'A'}


def test_worker_monitor_delivers_the_registered_shutdown_handler():
    program = '''
import multiprocessing, signal
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
observed = []
signal.signal(signal.SIGTERM, lambda *_: observed.append(True))
registry = WorkerRegistry(global_kill_flag=multiprocessing.Value('b', True), worker_mode=WorkerMode.PROCESS)
registry._child_monitor_loop()
registry.shutdown_all()
raise SystemExit(0 if observed else 2)
'''
    completed = subprocess.run([sys.executable, '-B', '-c', program], capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
