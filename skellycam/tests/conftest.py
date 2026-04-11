"""
Shared test fixtures for the skellycam test suite.

Builds a lightweight FastAPI app with the same routes as the real app
but WITHOUT the heavy lifespan (bytecode compilation, logging setup, etc).
"""
import multiprocessing
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import shutdown_router
from skellycam.api.routers import SKELLYCAM_ROUTERS


# ---------------------------------------------------------------------------
# Core mocks
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_global_kill_flag():
    """A real multiprocessing.Value used as the global kill flag."""
    return multiprocessing.Value("b", False)


@pytest.fixture()
def mock_worker_registry(mock_global_kill_flag):
    """A MagicMock standing in for WorkerRegistry (no real threads/processes)."""
    registry = MagicMock()
    registry.heartbeat_timestamp = multiprocessing.Value("d", 0.0)
    return registry


@pytest.fixture()
def mock_camera_group_manager():
    """
    A MagicMock standing in for CameraGroupManager.

    All async methods are AsyncMock so they can be awaited without error.
    Sync methods return sensible defaults.
    """
    mgr = MagicMock()
    # Async methods
    mgr.create_or_update_camera_group = AsyncMock()
    mgr.create_and_start_camera_group = AsyncMock()
    mgr.start_recording_all_groups = AsyncMock()
    def _mock_stats_recarray(mean=30.0):
        m = MagicMock()
        m.median_value = mean
        m.mean_value = mean
        m.standard_deviation_value = 1.0
        m.min_value = mean - 2.0
        m.max_value = mean + 2.0
        return m

    mock_recording_info = MagicMock()
    mock_recording_info.recording_name = "test_recording"
    mock_recording_info.full_recording_path = "/tmp/test_recording"

    mock_timestamp_stats = MagicMock()
    mock_timestamp_stats.number_of_cameras = 1
    mock_timestamp_stats.number_of_frames = 100
    mock_timestamp_stats.total_duration_sec = 10.0
    mock_timestamp_stats.framerate_stats = _mock_stats_recarray(30.0)
    mock_timestamp_stats.frame_duration_stats = _mock_stats_recarray(33.3)
    mock_timestamp_stats.inter_camera_grab_range_ms = _mock_stats_recarray(2.0)

    mgr.stop_recording_all_groups = AsyncMock(return_value=[(mock_recording_info, mock_timestamp_stats)])
    mgr.close_all_camera_groups = AsyncMock()
    mgr.pause_unpause_all_groups = AsyncMock()
    mgr.pause_all_groups = AsyncMock()
    mgr.unpause_all_groups = AsyncMock()

    # Sync methods
    mgr.get_latest_frontend_payloads = MagicMock(return_value={})
    mgr.get_backend_framerate_updates = MagicMock(return_value={})
    mgr.to_state_dict = MagicMock(return_value={"camera_groups": {}})
    mgr.camera_groups = {}
    return mgr


# ---------------------------------------------------------------------------
# FastAPI app + TestClient (lightweight — no lifespan)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(mock_global_kill_flag, mock_worker_registry, mock_camera_group_manager):
    """
    A lightweight FastAPI app with the same routes but no heavy lifespan.

    Patches `get_or_create_camera_group_manager` at every import site
    so all endpoints use the mock.
    """
    with patch(
        "skellycam.api.http.camera_group.camera_group_router.get_or_create_camera_group_manager",
        return_value=mock_camera_group_manager,
    ), patch(
        "skellycam.api.websocket.ws_server.get_or_create_camera_group_manager",
        return_value=mock_camera_group_manager,
    ), patch(
        "skellycam.api.websocket.ws_server.WebsocketServer._logs_relay",
        new_callable=AsyncMock,
    ):
        test_app = FastAPI()
        test_app.state.global_kill_flag = mock_global_kill_flag
        test_app.state.worker_registry = mock_worker_registry

        # Register the same routes as the real app (no prefix)
        for router in [health_router, shutdown_router]:
            test_app.include_router(router)

        for router in SKELLYCAM_ROUTERS:
            test_app.include_router(router)

        yield test_app


@pytest.fixture()
def client(app):
    """Synchronous TestClient for HTTP endpoint tests."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
