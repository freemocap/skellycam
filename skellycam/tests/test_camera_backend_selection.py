from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from skellycam.api.http.cameras.camera_router import CameraGroupCreateRequest
from skellycam.core.camera_group import camera_backend_manager as selection
from skellycam.core.camera_group import camera_group_manager as python_backend


class FakeManager:
    def __init__(self, **kwargs):
        self.camera_groups = {}

    async def create_or_update_camera_group(self, configs):
        group = SimpleNamespace(id="created", configs=configs)
        self.camera_groups[group.id] = group
        return group


def test_existing_api_requests_default_to_python_and_reject_unknown_engines():
    assert CameraGroupCreateRequest(camera_configs={}).backend == "python"
    with pytest.raises(ValidationError):
        CameraGroupCreateRequest(camera_configs={}, backend="tauri")


@pytest.mark.asyncio
async def test_selection_changes_group_factory_without_replacing_application_manager(monkeypatch):
    monkeypatch.setattr(python_backend, "CameraGroupManager", FakeManager)
    monkeypatch.setattr(selection, "RustCameraGroupManager", FakeManager)
    manager = selection.CameraBackendManager(global_kill_flag=None, worker_registry=None)
    identity = id(manager)
    original = manager._manager
    group = await manager.create_or_update_camera_group({}, backend="rust")
    assert id(manager) == identity
    assert manager.backend == "rust"
    assert manager._manager is not original
    assert manager.camera_groups[group.id] is group


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["python", "rust"])
async def test_shutdown_finalizes_native_recorders_before_signaling_process_exit(monkeypatch, backend):
    from fastapi import FastAPI, Request
    from skellycam.api.http.app import shutdown

    app = FastAPI()
    app.state.global_kill_flag = SimpleNamespace(value=False)
    finalized = []

    async def close():
        assert not app.state.global_kill_flag.value
        finalized.append(True)

    monkeypatch.setattr(python_backend, "_CAMERA_GROUP_MANAGER", SimpleNamespace(
        backend=backend, close_all_camera_groups=close,
    ))
    monkeypatch.setattr(shutdown.logger, "api", lambda *args: None, raising=False)
    request = Request({"type": "http", "method": "GET", "path": "/shutdown",
                       "headers": [], "scheme": "http", "server": ("localhost", 53117), "app": app})
    await shutdown.shutdown_server(request)
    assert finalized == ([True] if backend == "rust" else [])
    assert app.state.global_kill_flag.value


@pytest.mark.asyncio
async def test_selection_does_not_replace_a_group_that_owns_cameras(monkeypatch):
    monkeypatch.setattr(python_backend, "CameraGroupManager", FakeManager)
    manager = selection.CameraBackendManager(global_kill_flag=None, worker_registry=None)
    group = await manager.create_or_update_camera_group({})
    with pytest.raises(selection.CameraBackendInUseError, match="Close the current cameras"):
        await manager.create_or_update_camera_group({}, backend="rust")
    assert manager.backend == "python"
    assert manager.camera_groups[group.id] is group
