from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from skellycam.core.camera_group.rust_camera_group import RustCameraGroup, RustCameraGroupManager


def test_new_group_frames_are_not_hidden_by_an_older_groups_threshold():
    native = Mock()
    frames = {"old": (101, 123.0, b"old"), "new": (1, 124.0, b"new")}
    native.get_latest_frame_payloads.side_effect = lambda if_newer_than: {
        key: value for key, value in frames.items() if value[0] > if_newer_than
    }
    manager = RustCameraGroupManager.__new__(RustCameraGroupManager)
    manager._native = native
    manager.camera_groups = {"old": object(), "new": object()}
    manager.closing = False
    manager._framerate_timestamps = {}
    result = manager.get_latest_frontend_payloads({"old": 101})
    assert set(result) == {"new"}
    assert result["new"][2].readonly
    assert result["new"][2].tobytes() == b"new"


@pytest.mark.asyncio
async def test_close_finalizes_recording_then_releases_only_its_group():
    native = Mock()
    group = RustCameraGroup("selected", {}, native)
    group._recording_info = object()
    async def fail_finalization():
        group._recording_info = None
        raise RuntimeError("disk error")
    group.stop_recording = fail_finalization
    with pytest.raises(RuntimeError, match="disk error"):
        await group.close()
    native.close_group.assert_called_once_with("selected")
    native.close_all_groups.assert_not_called()
    await group.close()
    native.close_group.assert_called_once()


@pytest.mark.asyncio
async def test_closing_empty_manager_does_not_disable_future_polling():
    manager = RustCameraGroupManager.__new__(RustCameraGroupManager)
    manager.camera_groups = {}
    manager._framerate_timestamps = {}
    manager.closing = False
    await manager.close_all_camera_groups()
    assert not manager.closing
