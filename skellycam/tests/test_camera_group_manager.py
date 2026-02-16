"""Tests for CameraGroupManager logic (without real cameras)."""
import multiprocessing
from unittest.mock import MagicMock, patch

import pytest

from skellycam.core.camera_group.camera_group_manager import (
    CameraGroupManager,
    get_or_create_camera_group_manager,
)


@pytest.fixture()
def kill_flag():
    return multiprocessing.Value("b", False)


@pytest.fixture()
def process_registry():
    reg = MagicMock()
    reg.heartbeat_timestamp = multiprocessing.Value("d", 0.0)
    return reg


@pytest.fixture()
def manager(kill_flag, process_registry):
    return CameraGroupManager(
        global_kill_flag=kill_flag,
        process_registry=process_registry,
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


class TestSingletonFactory:
    def test_returns_same_instance(self, kill_flag, process_registry):
        """get_or_create_camera_group_manager returns the same instance on repeated calls."""
        # We need to reset the module-level singleton before testing
        with patch(
            "skellycam.core.camera_group.camera_group_manager._CAMERA_GROUP_MANAGER",
            None,
        ):
            from fastapi import FastAPI
            app = FastAPI()
            app.state.global_kill_flag = kill_flag
            app.state.process_registry = process_registry

            first = get_or_create_camera_group_manager(app)
            second = get_or_create_camera_group_manager(app)
            assert first is second
