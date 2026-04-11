"""Tests for CameraOrchestrator frame synchronization and recording logic."""

import pytest

from skellycam.core.camera_group.camera_group_helpers.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_group_helpers.camera_status import CameraStatus


def _make_orchestrator(camera_ids: list[str]) -> CameraOrchestrator:
    statuses = {cam_id: CameraStatus() for cam_id in camera_ids}
    return CameraOrchestrator.from_statuses(camera_statuses=statuses)


# ---------------------------------------------------------------------------
# CameraStatus
# ---------------------------------------------------------------------------

class TestCameraStatus:
    def test_default_is_not_ready(self) -> None:
        """A fresh CameraStatus is not ready (not connected)."""
        status = CameraStatus()
        assert status.ready is False

    def test_connected_status_is_ready(self) -> None:
        status = CameraStatus()
        status.connected.value = True
        assert status.ready is True

    def test_paused_status_is_not_ready(self) -> None:
        status = CameraStatus()
        status.connected.value = True
        status.should_pause.value = True
        assert status.ready is False

    def test_error_status_is_not_ready(self) -> None:
        status = CameraStatus()
        status.connected.value = True
        status.error.value = True
        assert status.ready is False

    def test_signal_error_sets_flags(self) -> None:
        status = CameraStatus()
        status.connected.value = True
        status.grabbing_frame.value = True
        status.signal_error()
        assert bool(status.error.value) is True
        assert bool(status.connected.value) is False
        assert bool(status.grabbing_frame.value) is False

    def test_signal_closing_sets_flags(self) -> None:
        status = CameraStatus()
        status.connected.value = True
        status.recording_in_progress.value = True
        status.signal_closing()
        assert bool(status.closing.value) is True
        assert bool(status.connected.value) is False
        assert bool(status.recording_in_progress.value) is False

    def test_serialize_returns_dict(self) -> None:
        status = CameraStatus()
        status.connected.value = True
        result = status.serialize()
        assert isinstance(result, dict)
        assert bool(result["connected"]) is True
        assert bool(result["closed"]) is False


# ---------------------------------------------------------------------------
# CameraOrchestrator — Frame Synchronization
# ---------------------------------------------------------------------------

class TestCameraOrchestratorSync:
    def test_not_ready_until_all_connected(self) -> None:
        orch = _make_orchestrator(["cam0", "cam1"])
        assert orch.all_ready is False

        orch.camera_statuses["cam0"].connected.value = True
        assert orch.all_ready is False

        orch.camera_statuses["cam1"].connected.value = True
        assert orch.all_ready is True

    def test_should_grab_blocks_when_not_all_ready(self) -> None:
        orch = _make_orchestrator(["cam0", "cam1"])
        orch.camera_statuses["cam0"].connected.value = True
        # cam1 not connected yet
        assert orch.should_grab_by_id("cam0") is False

    def test_should_grab_allows_slowest_camera(self) -> None:
        """The camera with the lowest frame count should be allowed to grab."""
        orch = _make_orchestrator(["cam0", "cam1"])
        for s in orch.camera_statuses.values():
            s.connected.value = True

        # cam0 at frame 5, cam1 at frame 7 — cam0 should grab (it's behind)
        orch.camera_statuses["cam0"].frame_count.value = 5
        orch.camera_statuses["cam1"].frame_count.value = 7
        assert orch.should_grab_by_id("cam0") is True
        # cam1 is ahead, so it should NOT grab yet
        assert orch.should_grab_by_id("cam1") is False

    def test_should_grab_allows_tied_cameras(self) -> None:
        """When all cameras are at the same frame count, all should be allowed to grab."""
        orch = _make_orchestrator(["cam0", "cam1", "cam2"])
        for s in orch.camera_statuses.values():
            s.connected.value = True
            s.frame_count.value = 10

        assert orch.should_grab_by_id("cam0") is True
        assert orch.should_grab_by_id("cam1") is True
        assert orch.should_grab_by_id("cam2") is True

    def test_should_grab_unknown_camera_raises(self) -> None:
        orch = _make_orchestrator(["cam0"])
        with pytest.raises(ValueError, match="not found"):
            orch.should_grab_by_id("nonexistent")

    def test_camera_frame_counts(self) -> None:
        orch = _make_orchestrator(["cam0", "cam1"])
        orch.camera_statuses["cam0"].frame_count.value = 100
        orch.camera_statuses["cam1"].frame_count.value = 102
        counts = orch.camera_frame_counts
        assert counts["cam0"] == 100
        assert counts["cam1"] == 102


# ---------------------------------------------------------------------------
# CameraOrchestrator — Recording Flags
# ---------------------------------------------------------------------------

class TestCameraOrchestratorRecording:
    def test_no_recording_by_default(self) -> None:
        orch = _make_orchestrator(["cam0"])
        should_record, should_finish = orch.should_record_frame_number(frame_number=50)
        assert should_record is False
        assert should_finish is False

    def test_recording_starts_at_first_frame(self) -> None:
        orch = _make_orchestrator(["cam0"])
        orch.first_recording_frame_number.value = 10
        # Frame before recording start
        should_record, should_finish = orch.should_record_frame_number(frame_number=9)
        assert should_record is False
        assert should_finish is False
        # Frame at recording start
        should_record, should_finish = orch.should_record_frame_number(frame_number=10)
        assert should_record is True
        assert should_finish is False

    def test_recording_stops_at_last_frame(self) -> None:
        orch = _make_orchestrator(["cam0"])
        orch.first_recording_frame_number.value = 10
        orch.last_recording_frame_number.value = 20
        # Frame inside recording range
        should_record, should_finish = orch.should_record_frame_number(frame_number=15)
        assert should_record is True
        assert should_finish is False
        # Frame at stop boundary
        should_record, should_finish = orch.should_record_frame_number(frame_number=20)
        assert should_record is False
        assert should_finish is True

    def test_recording_past_stop_boundary(self) -> None:
        orch = _make_orchestrator(["cam0"])
        orch.first_recording_frame_number.value = 10
        orch.last_recording_frame_number.value = 20
        should_record, should_finish = orch.should_record_frame_number(frame_number=25)
        assert should_record is False
        assert should_finish is True


# ---------------------------------------------------------------------------
# CameraOrchestrator — Pause/Unpause
# ---------------------------------------------------------------------------

class TestCameraOrchestratorPause:
    @pytest.mark.asyncio
    async def test_pause_and_unpause(self) -> None:
        orch = _make_orchestrator(["cam0", "cam1"])
        for s in orch.camera_statuses.values():
            s.connected.value = True

        # Manually simulate what the camera loop does:
        # When should_pause is set, the camera sets is_paused
        await orch.pause(await_paused=False)
        for s in orch.camera_statuses.values():
            assert bool(s.should_pause.value) is True
            # Simulate camera loop responding
            s.is_paused.value = True

        assert orch.all_cameras_paused is True

        await orch.unpause(await_unpaused=False)
        for s in orch.camera_statuses.values():
            assert bool(s.should_pause.value) is False
            # Simulate camera loop responding
            s.is_paused.value = False

        assert orch.any_cameras_paused is False
