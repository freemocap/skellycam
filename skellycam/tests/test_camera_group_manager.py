"""Tests for CameraGroupManager logic (without real cameras)."""
import multiprocessing
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_errors import CameraStateConflict
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from skellycam.core.camera_group.camera_group_manager import (
    CameraGroupManager,
    get_or_create_camera_group_manager,
)


@pytest.fixture()
def kill_flag():
    return multiprocessing.Value("b", False)


@pytest.fixture()
def worker_registry():
    reg = MagicMock(spec=WorkerRegistry)
    reg.heartbeat_timestamp = multiprocessing.Value("d", 0.0)
    return reg


@pytest.fixture()
def manager(kill_flag, worker_registry):
    return CameraGroupManager(
        global_kill_flag=kill_flag,
        worker_registry=worker_registry,
    )


class TestCameraGroupManagerInit:
    def test_starts_empty(self, manager):
        """New manager has no camera groups."""
        assert manager.camera_groups == {}
        assert manager.closing is False

    def test_get_nonexistent_group_raises(self, manager):
        """Requesting a nonexistent group raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            manager.get_camera_group("nonexistent-id")

    @pytest.mark.asyncio
    async def test_close_empty_groups(self, manager):
        """Closing with no groups should not raise."""
        await manager.close_all_camera_groups()
        assert manager.camera_groups == {}

    def test_to_state_dict_empty(self, manager):
        """State dict with no groups returns expected structure."""
        state = manager.to_state_dict()
        assert isinstance(state, dict)


REPORTED_30_FPS = 1e7 / 333333  # DirectShow's report for a camera opened at 30 fps


def open_group(manager, *, recording: bool):
    """Register an open OpenCV group whose camera reports 30 fps."""
    reported = {"A": CameraConfig(camera_id="A", camera_index=0, framerate=REPORTED_30_FPS)}
    group = Mock(spec=CameraGroup, id="open", camera_ids=list(reported), configs=reported,
                 recording_in_progress=recording, close=AsyncMock(), update_camera_settings=AsyncMock())
    manager.camera_groups["open"] = group
    manager.create_and_start_camera_group = AsyncMock()
    return group, reported


class TestFrameRateChanges:
    @pytest.mark.asyncio
    async def test_frame_rate_change_updates_the_open_group(self, manager):
        """Frame rate does not size shared memory: the open group reopens its streams in place."""
        group, reported = open_group(manager, recording=False)
        requested = {"A": reported["A"].model_copy(update={"framerate": 60.0})}
        assert await manager.create_or_update_camera_group(requested) is group
        group.update_camera_settings.assert_awaited_once_with(requested_configs=requested)
        group.close.assert_not_awaited()
        manager.create_and_start_camera_group.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_frame_rate_change_while_recording_is_refused(self, manager):
        """A recording's video declares one frame rate."""
        group, reported = open_group(manager, recording=True)
        requested = {"A": reported["A"].model_copy(update={"framerate": 60.0})}
        with pytest.raises(CameraStateConflict, match="frame rate"):
            await manager.create_or_update_camera_group(requested)
        group.update_camera_settings.assert_not_awaited()
        group.close.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("requested_rate", [30.0, REPORTED_30_FPS, -1.0])
    async def test_settings_with_the_running_frame_rate_still_apply_while_recording(self, manager, requested_rate):
        group, reported = open_group(manager, recording=True)
        requested = {"A": reported["A"].model_copy(update={"framerate": requested_rate, "exposure": -5})}
        assert await manager.create_or_update_camera_group(requested) is group
        group.update_camera_settings.assert_awaited_once_with(requested_configs=requested)


class TestSingletonFactory:
    def test_returns_same_instance(self, kill_flag, worker_registry):
        """get_or_create_camera_group_manager returns the same instance on repeated calls."""
        # We need to reset the module-level singleton before testing
        with patch(
            "skellycam.core.camera_group.camera_group_manager._CAMERA_GROUP_MANAGER",
            None,
        ):
            from fastapi import FastAPI
            app = FastAPI()
            app.state.global_kill_flag = kill_flag
            app.state.worker_registry = worker_registry

            first = get_or_create_camera_group_manager(app)
            second = get_or_create_camera_group_manager(app)
            assert first is second
