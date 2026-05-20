"""Hardware tests for the PyO3 Rust bridge (`_skellycam_rust`).

These tests require:
    1. At least one physical USB camera attached
    2. The Rust extension built: ``uv run poe rebuild``

Run with::

    uv run poe test skellycam/tests/test_rust_bridge.py

Skip hardware tests entirely::

    uv run poe test skellycam/tests/ -k "not hardware"
"""

import time

import pytest

# ── Module-level import guard ──────────────────────────────────────────────────
# Skip all tests if the Rust extension isn't built or imports fail.
_hardware_skip = pytest.mark.skipif(True, reason="placeholder — resolved at module level")

try:
    import _skellycam_rust

    # Test that the module loaded and has the expected API surface
    assert hasattr(_skellycam_rust, "CameraGroupManager"), "CameraGroupManager class missing"
    assert hasattr(_skellycam_rust, "detect_cameras"), "detect_cameras function missing"
    _RUST_AVAILABLE = True
except (ImportError, AssertionError) as e:
    _RUST_AVAILABLE = False
    _RUST_SKIP_REASON = f"_skellycam_rust not available: {e}"

# Detect cameras once at module load so we can skip if none are available
_CAMERAS = []
if _RUST_AVAILABLE:
    try:
        _CAMERAS = _skellycam_rust.detect_cameras()
    except Exception as e:
        _RUST_AVAILABLE = False
        _RUST_SKIP_REASON = f"Camera detection failed: {e}"

# Markers
requires_rust = pytest.mark.skipif(
    not _RUST_AVAILABLE,
    reason=_RUST_SKIP_REASON if not _RUST_AVAILABLE else "",
)
requires_cameras = pytest.mark.skipif(
    not _CAMERAS,
    reason="No USB cameras detected — hardware test requires at least one camera",
)
hardware = pytest.mark.hardware  # pytest marker for filtering


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config_dict(identity, width=1280, height=720, exposure=-7, framerate=-1.0):
    """Build a Python config dict matching what the Rust bridge expects."""
    return {
        identity["unique_identifier"]: {
            "camera_index": identity["camera_index"],
            "camera_id": identity["unique_identifier"],
            "width": width,
            "height": height,
            "exposure": exposure,
            "exposure_mode": "MANUAL",
            "framerate": framerate,
            "rotation": -1,
        }
    }


def _poll_until_frames(manager, target_count, timeout_secs=15):
    """Poll ``get_latest_frame_payloads`` until ``target_count`` new frames arrive."""
    start = time.monotonic()
    last_frame = -1
    count = 0

    while count < target_count:
        payloads = manager.get_latest_frame_payloads(if_newer_than=last_frame)
        for _group_id, (frame_number, _timestamp_ns, jpeg_bytes) in payloads.items():
            if frame_number > last_frame:
                last_frame = frame_number
                count += 1
                # Validate JPEG SOI marker (0xFF 0xD8)
                assert jpeg_bytes[:2] == b"\xff\xd8", (
                    f"Frame {frame_number} is not a valid JPEG"
                )

        if time.monotonic() - start > timeout_secs:
            pytest.fail(
                f"Timed out after {timeout_secs}s — got {count}/{target_count} frames"
            )
        time.sleep(0.001)

    return last_frame


# ── Tests ─────────────────────────────────────────────────────────────────────

@requires_rust
@pytest.mark.hardware
class TestDetectCameras:
    """Camera detection via the PyO3 bridge."""

    @requires_cameras
    def test_detect_returns_list_of_dicts(self):
        """``detect_cameras()`` returns a list of dicts with expected keys."""
        cameras = _skellycam_rust.detect_cameras()
        assert isinstance(cameras, list)
        assert len(cameras) > 0

        for cam in cameras:
            assert "camera_index" in cam
            assert "unique_identifier" in cam
            assert "device_path" in cam
            assert "display_name" in cam
            assert isinstance(cam["camera_index"], int)
            assert isinstance(cam["unique_identifier"], str)
            assert len(cam["unique_identifier"]) == 4  # 4-char hex ID


@requires_rust
@pytest.mark.hardware
class TestGroupLifecycle:
    """Create → poll → shutdown cycle."""

    @requires_cameras
    def test_create_group_and_poll_frames(self):
        """Create a camera group, stream frames, verify valid JPEGs, shut down."""
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])

        group_id = manager.create_or_update_group(configs)
        assert isinstance(group_id, str)
        assert len(group_id) == 6  # short UUID

        # Poll for 10 frames — validates JPEG headers internally
        last_frame = _poll_until_frames(manager, 10)
        assert last_frame >= 9  # 0-indexed: 10 frames → last is at least 9

        manager.close_all_groups()

    @requires_cameras
    def test_pause_unpause_stops_and_resumes_frames(self):
        """Paused groups should not advance frame numbers; unpaused ones should."""
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])

        group_id = manager.create_or_update_group(configs)

        # Stream a few frames
        _poll_until_frames(manager, 5)

        # Snapshot the current frame number
        payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
        before = payloads[group_id][0] if payloads else -1

        # Pause and wait — frame number should not advance
        manager.pause()
        time.sleep(0.5)
        payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
        during = payloads[group_id][0] if payloads else before
        assert during == before, f"Frame advanced from {before} to {during} while paused"

        # Unpause — frames should resume
        manager.unpause()
        _poll_until_frames(manager, 5)

        manager.close_all_groups()

    @requires_cameras
    def test_multiple_groups_coexist(self):
        """Multiple camera groups can run concurrently."""
        if len(_CAMERAS) < 2:
            pytest.skip("Need 2+ cameras for multi-group test")

        manager = _skellycam_rust.CameraGroupManager()

        # Create two groups, each with one camera
        configs_a = _make_config_dict(_CAMERAS[0])
        configs_b = _make_config_dict(_CAMERAS[1])

        id_a = manager.create_or_update_group(configs_a)
        id_b = manager.create_or_update_group(configs_b)
        assert id_a != id_b

        # Both groups should produce frames
        _poll_until_frames(manager, 10)

        groups = manager.list_groups()
        assert len(groups) == 2

        manager.close_all_groups()

    @requires_cameras
    def test_to_state_dict(self):
        """``to_state_dict`` returns serializable state with expected keys."""
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])

        group_id = manager.create_or_update_group(configs)
        _poll_until_frames(manager, 3)

        state = manager.to_state_dict()
        assert "camera_groups" in state
        assert group_id in state["camera_groups"]

        group_state = state["camera_groups"][group_id]
        assert "cameras" in group_state
        assert group_state["camera_count"] == 1

        manager.close_all_groups()

    @requires_cameras
    def test_apply_configs_update_exposure(self):
        """Apply a new exposure value to a running group; frames continue to flow."""
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])

        group_id = manager.create_or_update_group(configs)
        _poll_until_frames(manager, 5)

        # Change exposure from -7 to -5
        updated = {
            _CAMERAS[0]["unique_identifier"]: {
                "camera_index": _CAMERAS[0]["camera_index"],
                "camera_id": _CAMERAS[0]["unique_identifier"],
                "width": 1280,
                "height": 720,
                "exposure": -5,
                "exposure_mode": "MANUAL",
                "framerate": -1.0,
                "rotation": -1,
            }
        }
        manager.apply_configs(group_id, updated)

        # Frames should still flow after config change
        _poll_until_frames(manager, 5)
        manager.close_all_groups()

    @requires_cameras
    def test_detect_then_apply_matches_api_flow(self):
        """Detect cameras, build a config dict from detection result, apply it."""
        cameras = _skellycam_rust.detect_cameras()
        assert len(cameras) > 0

        # Build a config dict exactly like the HTTP /group/apply endpoint
        cam = cameras[0]
        configs = {
            cam["unique_identifier"]: {
                "camera_id": cam["unique_identifier"],
                "camera_index": cam["camera_index"],
                "width": 1280,
                "height": 720,
                "exposure": -7,
                "exposure_mode": "MANUAL",
                "framerate": -1.0,
                "rotation": -1,
            }
        }

        manager = _skellycam_rust.CameraGroupManager()
        group_id = manager.create_or_update_group(configs)
        assert isinstance(group_id, str)
        assert len(group_id) == 6

        # Verify frames flow from the detected-and-applied camera
        _poll_until_frames(manager, 10)
        manager.close_all_groups()


@requires_rust
@pytest.mark.hardware
class TestRecording:
    """Recording lifecycle via the PyO3 bridge."""

    @requires_cameras
    def test_start_stop_recording(self):
        """Start recording, stream frames, stop, verify summary structure."""
        import tempfile
        import os

        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])

        group_id = manager.create_or_update_group(configs)

        # Record to a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            manager.start_recording(output_dir=tmpdir, label="pytest_session")

            # Stream frames while recording
            _poll_until_frames(manager, 30)

            result = manager.stop_recording()

            # Result is a dict mapping group_id → summary dict
            assert group_id in result
            summary = result[group_id]
            assert "total_frames_per_camera" in summary
            assert "video_paths" in summary
            assert "csv_paths" in summary

        manager.close_all_groups()

    @requires_cameras
    def test_full_record_cycle_returns_stop_recording_response(self):
        """Start → stream 60 frames → stop → verify result matches StopRecordingResponse schema."""
        import tempfile

        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])
        group_id = manager.create_or_update_group(configs)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager.start_recording(output_dir=tmpdir, label="schema_test")
            _poll_until_frames(manager, 60)
            result = manager.stop_recording()

            assert group_id in result
            summary = result[group_id]

            # All keys required by the OpenAPI StopRecordingResponse
            required_keys = [
                "total_frames_per_camera",
                "video_paths",
                "csv_paths",
                "info_json_path",
            ]
            for key in required_keys:
                assert key in summary, f"Missing key in stop_recording result: {key}"

            # total_frames_per_camera should be a positive integer
            assert isinstance(summary["total_frames_per_camera"], int)
            assert summary["total_frames_per_camera"] > 0

            # video_paths should be a non-empty list of strings
            assert isinstance(summary["video_paths"], list)
            assert len(summary["video_paths"]) > 0

        manager.close_all_groups()

    @requires_cameras
    def test_record_creates_video_files(self):
        """Start recording, stream frames, stop — verify .mp4 files exist on disk."""
        import tempfile
        import os as _os

        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config_dict(_CAMERAS[0])
        manager.create_or_update_group(configs)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager.start_recording(output_dir=tmpdir, label="file_test")
            _poll_until_frames(manager, 60)
            result = manager.stop_recording()

            group_ids = list(result.keys())
            assert len(group_ids) > 0
            summary = result[group_ids[0]]

            for video_path in summary.get("video_paths", []):
                assert _os.path.isfile(video_path), f"Video file not found: {video_path}"
                file_size = _os.path.getsize(video_path)
                assert file_size > 0, f"Video file is empty: {video_path}"

        manager.close_all_groups()
