from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.camera_group.camera_backend_manager import CameraBackendManager
from skellycam.core.camera_group.rust_camera_group import RustCameraGroupManager
from skellycam.core.camera_group.camera_errors import CameraStateConflict
import asyncio


def test_reads_never_stop_or_toggle_cameras(client, mock_camera_group_manager):
    assert client.get('/skellycam/camera/group/all/record/stop').status_code == 405
    assert client.get('/skellycam/camera/group/all/pause').status_code == 405
    assert client.get('/skellycam/camera/group/all/pause_unpause').status_code == 404
    mock_camera_group_manager.stop_recording_all_groups.assert_not_awaited()
    mock_camera_group_manager.set_paused_all_groups.assert_not_awaited()
    mock_camera_group_manager.pause_unpause_all_groups.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_start_cannot_overwrite_recording_before_worker_flags_update():
    manager = CameraBackendManager.__new__(CameraBackendManager)
    manager._configuration_lock = asyncio.Lock()
    manager._recording_requested = False
    manager._manager = SimpleNamespace(camera_groups={'group': SimpleNamespace(recording_in_progress=False)},
        start_recording_all_groups=AsyncMock(), stop_recording_all_groups=AsyncMock(return_value=['saved']),
        close_all_camera_groups=AsyncMock())
    await manager.start_recording_all_groups('first')
    with pytest.raises(CameraStateConflict, match='already'):
        await manager.start_recording_all_groups('second')
    manager._manager.start_recording_all_groups.assert_awaited_once_with('first')
    assert await manager.stop_recording_all_groups() == ['saved']
    with pytest.raises(CameraStateConflict, match='No recording'):
        await manager.stop_recording_all_groups()
    await manager.start_recording_all_groups('next')
    await manager.close_all_camera_groups()
    assert manager._recording_requested is False


@pytest.mark.parametrize('command', ['start', 'stop'])
def test_recording_conflicts_return_409(client, mock_camera_group_manager, command, tmp_path):
    getattr(mock_camera_group_manager, f'{command}_recording_all_groups').side_effect = CameraStateConflict('conflict')
    response = client.post(f'/skellycam/camera/group/all/record/{command}',
        json={'recording_name': 'test', 'recording_directory': str(tmp_path), 'mic_device_index': -1} if command == 'start' else None)
    assert response.status_code == 409


def test_pause_requests_are_explicit_and_repeatable(client, mock_camera_group_manager):
    for desired in (True, True, False, False):
        response = client.put('/skellycam/camera/group/all/pause', json={'paused': desired})
        assert response.status_code == 200
        assert response.json() == {'paused': desired}
    assert mock_camera_group_manager.set_paused_all_groups.await_args_list == [
        call(paused=value) for value in (True, True, False, False)]
    for body in ({}, {'paused': 'false'}, {'paused': 1}):
        assert client.put('/skellycam/camera/group/all/pause', json=body).status_code == 422
    assert mock_camera_group_manager.set_paused_all_groups.await_count == 4


@pytest.mark.asyncio
async def test_python_backend_sets_every_group_to_requested_state():
    manager = CameraGroupManager.__new__(CameraGroupManager)
    group = CameraGroup.__new__(CameraGroup)
    group.cameras = SimpleNamespace(pause=AsyncMock(), unpause=AsyncMock())
    manager.camera_groups = {'group': group}
    wrapper = CameraBackendManager.__new__(CameraBackendManager)
    wrapper._manager = manager
    for desired in (True, True, False, False):
        await wrapper.set_paused_all_groups(paused=desired)
    assert group.cameras.pause.await_args_list == [call(await_paused=True)] * 2
    assert group.cameras.unpause.await_args_list == [call(await_unpaused=True)] * 2


@pytest.mark.asyncio
async def test_native_backend_repeated_pause_does_not_toggle():
    manager = RustCameraGroupManager.__new__(RustCameraGroupManager)
    manager._native = Mock()
    for desired in (True, True, False, False):
        await manager.set_paused_all_groups(paused=desired)
    assert manager._native.method_calls == [call.pause(), call.pause(), call.unpause(), call.unpause()]
