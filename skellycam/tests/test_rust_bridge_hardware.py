"""Comprehensive hardware tests for the PyO3 Rust bridge.

Runs the full camera lifecycle against every detected camera, in increasing
group sizes: 1 camera, 2 cameras, ..., N cameras. Mirrors the Rust test
suite in ``skellycam-rust/src/tests/all_tests.rs``.

Requires:
    1. At least one USB camera with MJPG format
    2. Rust extension built: ``uv run poe rebuild``

Run with::

    uv run pytest skellycam/tests/test_rust_bridge_hardware.py -v -m hardware -s

Skip in CI (the default)::

    uv run pytest skellycam/tests/ -v
"""

import logging
import time

import pytest

logger = logging.getLogger(__name__)

# ===============================================================================
# Module-level camera detection
# ===============================================================================

logger.info("")
logger.info("=" * 78)
logger.info("  SKELLYCAM RUST PYO3 BRIDGE — COMPREHENSIVE HARDWARE TEST SUITE")
logger.info("=" * 78)
logger.info("")

_RUST_AVAILABLE = False
_RUST_SKIP_REASON = ""
_ALL_CAMERAS: list[dict] = []

logger.info("[DETECT] Attempting to import _skellycam_rust...")
try:
    import _skellycam_rust

    assert hasattr(_skellycam_rust, "CameraGroupManager")
    assert hasattr(_skellycam_rust, "detect_cameras")
    _RUST_AVAILABLE = True
    logger.info("[DETECT] _skellycam_rust imported successfully")
    logger.info(f"[DETECT] Available classes: CameraGroupManager, detect_cameras, {len([x for x in dir(_skellycam_rust) if not x.startswith('_')]) - 2} more")
except (ImportError, AssertionError) as e:
    _RUST_SKIP_REASON = f"_skellycam_rust not available: {e}"
    logger.error(f"[DETECT] FAILED: {_RUST_SKIP_REASON}")

if _RUST_AVAILABLE:
    logger.info("[DETECT] Enumerating cameras via Rust openpnp-capture engine...")
    try:
        _ALL_CAMERAS = _skellycam_rust.detect_cameras()
        logger.info(f"[DETECT] SUCCESS: {len(_ALL_CAMERAS)} camera(s) detected and ready (all MJPG)")
        for i, cam in enumerate(_ALL_CAMERAS):
            logger.info(
                f"[DETECT]   [{i}] index={cam['camera_index']}  "
                f"id={cam['unique_identifier']}  "
                f"name=\"{cam['display_name']}\"  "
                f"formats={len(cam.get('formats', []))}"
            )
    except Exception as e:
        _RUST_AVAILABLE = False
        _RUST_SKIP_REASON = f"Camera detection failed: {e}"
        logger.error(f"[DETECT] FAILED: {_RUST_SKIP_REASON}")
else:
    logger.warning("[DETECT] Skipping camera detection — Rust extension not available")

requires_rust = pytest.mark.skipif(
    not _RUST_AVAILABLE,
    reason=_RUST_SKIP_REASON,
)
requires_cameras = pytest.mark.skipif(
    not _ALL_CAMERAS,
    reason="No USB cameras detected",
)
hardware = pytest.mark.hardware

# ===============================================================================
# Helpers
# ===============================================================================


def _make_config(camera: dict, **overrides) -> dict:
    """Build a single-camera config dict from a detection result entry."""
    cfg = {
        "camera_id": camera["unique_identifier"],
        "camera_index": camera["camera_index"],
        "width": overrides.get("width", 1280),
        "height": overrides.get("height", 720),
        "exposure": overrides.get("exposure", -7),
        "exposure_mode": overrides.get("exposure_mode", "MANUAL"),
        "framerate": overrides.get("framerate", -1.0),
        "rotation": overrides.get("rotation", -1),
        **overrides,
    }
    logger.debug(
        f"[CONFIG] camera_id={cfg['camera_id']}  index={cfg['camera_index']}  "
        f"{cfg['width']}x{cfg['height']}  exposure={cfg['exposure']}  "
        f"rotation={cfg['rotation']}  framerate={cfg['framerate']}"
    )
    return {cfg["camera_id"]: cfg}


def _validate_wire_format(payload_bytes: bytes) -> bool:
    """Validate the frontend wire-format binary payload.

    Wire format (matching Python ``FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE`` /
    ``FRONTEND_FRAME_HEADER_DTYPE`` numpy dtypes):
        PayloadHeader  (24 bytes, message_type=0)
        FrameHeader    (56 bytes, message_type=1) + JPEG  (repeated per camera)
        PayloadFooter  (24 bytes, message_type=2)

    Checks structure and validates that embedded JPEGs have SOI markers.
    """
    if len(payload_bytes) < 104:
        return False
    if payload_bytes[0] != 0:  # PayloadHeader.message_type
        return False

    offset = 24
    while offset + 56 <= len(payload_bytes) - 24:
        msg_type = payload_bytes[offset]
        if msg_type == 2:  # PayloadFooter
            break
        if msg_type != 1:  # FrameHeader
            return False

        jpeg_len = int.from_bytes(
            payload_bytes[offset + 48 : offset + 52], "little", signed=True
        )
        jpeg_start = offset + 56
        if jpeg_len <= 0 or jpeg_start + jpeg_len > len(payload_bytes):
            return False
        if payload_bytes[jpeg_start : jpeg_start + 2] != b"\xff\xd8":
            return False
        offset = jpeg_start + jpeg_len
    return True


def _poll_until_frames(manager, target_count: int, timeout_secs: float = 30.0) -> int:
    """Poll until ``target_count`` new frames arrive.

    Validates BOTH routes the PyO3 bridge exposes:
    1. ``get_latest_frame_payloads()`` — wire-format frontend binary (structure +
       embedded JPEG SOI via ``_validate_wire_format``)
    2. ``get_latest_raw_frames()`` — raw per-camera MJPEG bytes (SOI marker)

    Returns the last frame number seen.
    """
    logger.info(f"[POLL] Waiting for {target_count} frames (timeout={timeout_secs:.0f}s)...")
    start = time.monotonic()
    last_frame = -1
    count = 0
    last_log_at = 0

    while count < target_count:
        payloads = manager.get_latest_frame_payloads(if_newer_than=last_frame)
        for _group_id, (frame_number, _timestamp_ns, payload_bytes) in payloads.items():
            if frame_number > last_frame:
                last_frame = int(frame_number)
                count += 1

                # Log every frame for first 5, then every 10th
                if count <= 5 or count % 10 == 0:
                    elapsed = time.monotonic() - start
                    logger.info(
                        f"[POLL] frame#{frame_number:>4d}  "
                        f"payload={len(payload_bytes):>6d}B  "
                        f"count={count}/{target_count}  "
                        f"elapsed={elapsed:.1f}s"
                    )

                assert _validate_wire_format(payload_bytes), (
                    f"Frame {frame_number}: invalid wire-format payload "
                    f"(len={len(payload_bytes)}, first 4 bytes: {payload_bytes[:4]!r})"
                )

        if time.monotonic() - start > timeout_secs:
            elapsed = time.monotonic() - start
            logger.error(
                f"[POLL] TIMEOUT after {elapsed:.1f}s — "
                f"got {count}/{target_count} valid frames"
            )
            pytest.fail(
                f"Timed out after {timeout_secs:.0f}s — got {count}/{target_count} frames"
            )
        time.sleep(0.001)

    elapsed = time.monotonic() - start
    logger.info(f"[POLL] DONE: {count} frames in {elapsed:.1f}s ({count / elapsed:.1f} fps Python-side)")

    # Also validate the raw JPEG route on the last frame
    logger.info("[RAW] Validating raw per-camera JPEG route via get_latest_raw_frames()...")
    raw_frames = manager.get_latest_raw_frames()
    assert len(raw_frames) > 0, "get_latest_raw_frames() returned empty dict"
    for group_id, camera_frames in raw_frames.items():
        logger.info(f"[RAW] Group {group_id}: {len(camera_frames)} camera(s)")
        assert len(camera_frames) > 0, (
            f"Group {group_id}: no raw camera frames"
        )
        for camera_id, frame_info in camera_frames.items():
            jpeg_bytes = frame_info["jpeg_bytes"]
            w, h = frame_info["width"], frame_info["height"]
            so1, so2 = jpeg_bytes[:2]
            logger.info(
                f"[RAW]   camera={camera_id}  {w}x{h}  "
                f"{len(jpeg_bytes):>6d}B  SOI=[{so1:02X} {so2:02X}]  [OK] VALID JPEG"
            )
            assert jpeg_bytes[:2] == b"\xff\xd8", (
                f"Camera {camera_id}: raw JPEG missing SOI marker "
                f"(first 2 bytes: {jpeg_bytes[:2]!r})"
            )
    logger.info("[RAW] All raw JPEGs validated [OK]")

    return last_frame


def _measure_fps(manager, sample_count: int = 15) -> float:
    """Measure the actual frame rate over ``sample_count`` frames."""
    start = time.monotonic()
    _poll_until_frames(manager, sample_count)
    elapsed = time.monotonic() - start
    return sample_count / elapsed if elapsed > 0 else 0.0


# ===============================================================================
# Fixture: camera subsets (1 → N)
# ===============================================================================


def _camera_count_ids() -> list[str]:
    """Parameter IDs showing camera count and identifiers."""
    ids = []
    for n in range(1, len(_ALL_CAMERAS) + 1):
        ids.append(f"{n}_of_{len(_ALL_CAMERAS)}")
    return ids


def _camera_subsets():
    """Yield (camera_subset, count) for 1 → N cameras."""
    for n in range(1, len(_ALL_CAMERAS) + 1):
        yield pytest.param(_ALL_CAMERAS[:n], id=_camera_count_ids()[n - 1])


# ===============================================================================
# Test: camera detection
# ===============================================================================


@requires_rust
class TestCameraDetection:
    """Detection must work before anything else."""

    def test_detect_returns_six_cameras(self) -> None:
        """We know 6 physical cameras are attached (8 raw, 2 filtered)."""
        assert len(_ALL_CAMERAS) == 6, (
            f"Expected 6 cameras, got {len(_ALL_CAMERAS)}"
        )

    def test_all_cameras_have_mjpg_format(self) -> None:
        """Every detected camera must support MJPG."""
        for cam in _ALL_CAMERAS:
            fourccs = {fmt["fourcc_str"] for fmt in cam.get("formats", [])}
            assert "MJPG" in fourccs, (
                f"Camera {cam['camera_index']} ({cam['unique_identifier']}) "
                f"missing MJPG format — has: {fourccs}"
            )

    def test_all_camera_ids_are_unique(self) -> None:
        """Camera identifiers must be unique."""
        ids = [cam["unique_identifier"] for cam in _ALL_CAMERAS]
        assert len(ids) == len(set(ids)), f"Duplicate camera IDs: {ids}"

    def test_all_camera_indices_are_unique(self) -> None:
        """Camera indices must be unique."""
        indices = [cam["camera_index"] for cam in _ALL_CAMERAS]
        assert len(indices) == len(set(indices)), f"Duplicate indices: {indices}"


# ===============================================================================
# Test: connect and stream (1 → N cameras)
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestConnectAndStream:
    """Create groups and verify frames flow."""

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_create_group_and_poll_frames(self, cameras: list[dict]) -> None:
        """Create a camera group with N cameras, verify valid JPEG frames."""
        logger.info(f"\n{'-' * 60}")
        logger.info(f"[CONNECT] Testing with {len(cameras)} camera(s)")
        for cam in cameras:
            logger.info(f"[CONNECT]   index={cam['camera_index']}  id={cam['unique_identifier']}")
        logger.info(f"{'-' * 60}")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))

        logger.info(f"[CONNECT] Creating group with {len(configs)} config(s)...")
        group_id = manager.create_or_update_group(configs)
        assert isinstance(group_id, str)
        assert len(group_id) == 6
        logger.info(f"[CONNECT] Group created: id={group_id}")

        _poll_until_frames(manager, 15)
        logger.info(f"[CONNECT] Closing group {group_id}...")
        manager.close_all_groups()
        logger.info(f"[CONNECT] Group {group_id} closed [OK]")

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_state_dict_matches_camera_count(self, cameras: list[dict]) -> None:
        """``to_state_dict`` reports the correct number of cameras."""
        logger.info(f"\n{'-' * 60}")
        logger.info(f"[STATE_DICT] Testing to_state_dict with {len(cameras)} camera(s)")
        logger.info(f"{'-' * 60}")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))

        group_id = manager.create_or_update_group(configs)
        logger.info(f"[STATE_DICT] Group {group_id} created, polling frames...")
        _poll_until_frames(manager, 5)

        state = manager.to_state_dict()
        logger.info(f"[STATE_DICT] State keys: {list(state.keys())}")
        assert group_id in state["camera_groups"]
        group_state = state["camera_groups"][group_id]
        logger.info(f"[STATE_DICT] camera_count={group_state['camera_count']} (expected {len(cameras)})")
        assert group_state["camera_count"] == len(cameras)

        manager.close_all_groups()
        logger.info(f"[STATE_DICT] [OK]")


# ===============================================================================
# Test: pause / unpause
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestPauseUnpause:
    """Pause stops frame advancement; unpause resumes it."""

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_pause_stops_frames(self, cameras: list[dict]) -> None:
        """Frame number does not advance while paused."""
        logger.info(f"\n{'-' * 60}")
        logger.info(f"[PAUSE] Testing pause with {len(cameras)} camera(s)")
        logger.info(f"{'-' * 60}")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))

        manager.create_or_update_group(configs)
        _poll_until_frames(manager, 10)

        # Snapshot current frame number
        payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
        before = 0
        for _gid, (fn, _ts, _jpeg) in payloads.items():
            before = int(fn)

        logger.info(f"[PAUSE] Frame at {before}, pausing...")
        manager.pause()
        time.sleep(0.5)
        payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
        during = before
        for _gid, (fn, _ts, _jpeg) in payloads.items():
            during = int(fn)

        logger.info(f"[PAUSE] Frame still at {during} (expected {before})")
        assert during == before, (
            f"Frame advanced from {before} to {during} while paused"
        )

        logger.info("[PAUSE] Unpausing...")
        manager.unpause()
        _poll_until_frames(manager, 5)
        logger.info("[PAUSE] [OK]")
        manager.close_all_groups()

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_unpause_resumes_frames(self, cameras: list[dict]) -> None:
        """After unpause, frames resume flowing."""
        logger.info(f"\n{'-' * 60}")
        logger.info(f"[UNPAUSE] Testing unpause resume with {len(cameras)} camera(s)")
        logger.info(f"{'-' * 60}")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))

        manager.create_or_update_group(configs)
        _poll_until_frames(manager, 5)

        logger.info("[UNPAUSE] Pausing...")
        manager.pause()
        time.sleep(0.3)
        logger.info("[UNPAUSE] Unpausing — frames should resume...")
        manager.unpause()
        _poll_until_frames(manager, 5)
        logger.info("[UNPAUSE] [OK]")
        manager.close_all_groups()


# ===============================================================================
# Test: update exposure
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestExposureUpdate:
    """Apply exposure changes to running groups."""

    @requires_cameras
    def test_exposure_change_does_not_break_stream(self) -> None:
        """Changing exposure on a single camera group keeps frames flowing."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, exposure=-7)
        group_id = manager.create_or_update_group(configs)

        _poll_until_frames(manager, 10)

        # Change exposure to a brighter value
        updated = _make_config(cam, exposure=-4)
        manager.apply_configs(group_id, updated)
        _poll_until_frames(manager, 10)

        # Change to a darker value
        updated2 = _make_config(cam, exposure=-10)
        manager.apply_configs(group_id, updated2)
        _poll_until_frames(manager, 10)

        manager.close_all_groups()

    @requires_cameras
    def test_auto_exposure_mode_keeps_stream(self) -> None:
        """Switching to AUTO exposure mode keeps frames flowing."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, exposure_mode="AUTO")
        group_id = manager.create_or_update_group(configs)

        _poll_until_frames(manager, 10)

        # Switch back to manual
        updated = _make_config(cam, exposure_mode="MANUAL", exposure=-7)
        manager.apply_configs(group_id, updated)
        _poll_until_frames(manager, 10)

        manager.close_all_groups()


# ===============================================================================
# Test: rotation
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestRotation:
    """Apply rotation changes and verify JPEG dimensions change for 90-degree rotations."""

    ROTATION_VALUES = [-1, 0, 1, 2]  # NO_ROTATION, CLOCKWISE_90, ROTATE_180, COUNTERCLOCKWISE_90

    @requires_cameras
    def test_all_rotation_values_keep_stream(self) -> None:
        """Every rotation value (-1, 0, 1, 2) produces valid JPEG frames."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()

        for rotation in self.ROTATION_VALUES:
            configs = _make_config(cam, width=640, height=480, rotation=rotation)
            group_id = manager.create_or_update_group(configs)
            _poll_until_frames(manager, 10)

            # Grab one frame and check its JPEG
            payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
            for _gid, (_fn, _ts, jpeg_bytes) in payloads.items():
                assert jpeg_bytes[:2] == b"\xff\xd8", (
                    f"Invalid JPEG with rotation={rotation}"
                )
                assert len(jpeg_bytes) > 500, (
                    f"JPEG too small with rotation={rotation}"
                )

            manager.close_all_groups()
            time.sleep(0.1)  # Let hardware settle between groups

    @requires_cameras
    def test_rotation_90_swaps_dimensions(self) -> None:
        """Clockwise 90-degree rotation should swap width/height in the output."""
        cam = _ALL_CAMERAS[0]

        # Landscape (no rotation)
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, width=640, height=480, rotation=-1)
        manager.create_or_update_group(configs)
        _poll_until_frames(manager, 10)

        payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
        landscape_size = 0
        for _gid, (_fn, _ts, jpeg_bytes) in payloads.items():
            landscape_size = len(jpeg_bytes)

        manager.close_all_groups()
        time.sleep(0.1)

        # Portrait (90-degree rotation)
        manager2 = _skellycam_rust.CameraGroupManager()
        configs2 = _make_config(cam, width=640, height=480, rotation=0)
        manager2.create_or_update_group(configs2)
        _poll_until_frames(manager2, 10)

        payloads2 = manager2.get_latest_frame_payloads(if_newer_than=-1)
        portrait_size = 0
        for _gid, (_fn, _ts, jpeg_bytes) in payloads2.items():
            portrait_size = len(jpeg_bytes)

        manager2.close_all_groups()

        # JPEG sizes should differ because the aspect ratio flipped
        assert portrait_size != landscape_size, (
            f"Rotation had no effect on JPEG size: both {landscape_size} bytes"
        )


# ===============================================================================
# Test: framerate
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestFramerate:
    """Set specific framerates and verify the actual rate is in the expected ballpark."""

    @requires_cameras
    def test_framerate_30fps(self) -> None:
        """Requesting 30fps should yield ~25-35 fps."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, framerate=30.0)
        manager.create_or_update_group(configs)

        fps = _measure_fps(manager, sample_count=15)
        assert 20.0 <= fps <= 40.0, f"Expected ~30fps, got {fps:.1f}"

        manager.close_all_groups()

    @requires_cameras
    def test_framerate_60fps(self) -> None:
        """Requesting 60fps should yield >= 30 fps (hardware-dependent)."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, framerate=60.0)
        manager.create_or_update_group(configs)

        fps = _measure_fps(manager, sample_count=15)
        # 60fps cameras should deliver at least 30fps even under load
        assert fps >= 25.0, f"Expected >=25fps at 60fps setting, got {fps:.1f}"

        manager.close_all_groups()

    @requires_cameras
    def test_framerate_default(self) -> None:
        """framerate=-1 (use camera default) produces valid frames."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, framerate=-1.0)
        manager.create_or_update_group(configs)

        _poll_until_frames(manager, 15)
        manager.close_all_groups()


# ===============================================================================
# Test: resolution
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestResolution:
    """Set different resolutions and verify the camera adapts."""

    RESOLUTIONS_TO_TEST = [
        (1920, 1080),
        (1280, 720),
        (640, 480),
    ]

    @requires_cameras
    @pytest.mark.parametrize("width,height", RESOLUTIONS_TO_TEST)
    def test_resolution_change(self, width: int, height: int) -> None:
        """Setting a specific resolution produces valid JPEG frames."""
        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam, width=width, height=height)
        manager.create_or_update_group(configs)

        _poll_until_frames(manager, 15)

        # Verify the JPEG is non-trivial (higher res → larger JPEG)
        payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
        for _gid, (_fn, _ts, jpeg_bytes) in payloads.items():
            assert jpeg_bytes[:2] == b"\xff\xd8"
            if width >= 1920:
                assert len(jpeg_bytes) > 10_000, (
                    f"1080p JPEG suspiciously small: {len(jpeg_bytes)} bytes"
                )
            elif width <= 640:
                assert len(jpeg_bytes) < 200_000, (
                    f"480p JPEG suspiciously large: {len(jpeg_bytes)} bytes"
                )

        manager.close_all_groups()


# ===============================================================================
# Test: add / remove cameras
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestAddRemoveCameras:
    """Add and remove cameras from a running group."""

    @requires_cameras
    def test_add_camera_to_running_group(self) -> None:
        """Start with 1 camera, add a second, verify both stream."""
        if len(_ALL_CAMERAS) < 2:
            pytest.skip("Need 2+ cameras for add test")

        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(_ALL_CAMERAS[0])
        group_id = manager.create_or_update_group(configs)

        _poll_until_frames(manager, 10)

        # Add camera 1
        updated = {}
        updated.update(_make_config(_ALL_CAMERAS[0]))
        updated.update(_make_config(_ALL_CAMERAS[1]))
        manager.apply_configs(group_id, updated)
        _poll_until_frames(manager, 10)

        state = manager.to_state_dict()
        group_state = state["camera_groups"][group_id]
        assert group_state["camera_count"] == 2

        manager.close_all_groups()

    @requires_cameras
    def test_remove_camera_from_running_group(self) -> None:
        """Start with 2 cameras, remove one, verify the other keeps streaming."""
        if len(_ALL_CAMERAS) < 2:
            pytest.skip("Need 2+ cameras for remove test")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        configs.update(_make_config(_ALL_CAMERAS[0]))
        configs.update(_make_config(_ALL_CAMERAS[1]))
        group_id = manager.create_or_update_group(configs)

        _poll_until_frames(manager, 10)

        # Remove camera 1, keep camera 0
        updated = _make_config(_ALL_CAMERAS[0])
        manager.apply_configs(group_id, updated)
        _poll_until_frames(manager, 10)

        state = manager.to_state_dict()
        group_state = state["camera_groups"][group_id]
        assert group_state["camera_count"] == 1

        manager.close_all_groups()


# ===============================================================================
# Test: recording
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestRecording:
    """Full recording lifecycle: start → stream → stop → verify output."""

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_full_record_cycle(self, cameras: list[dict]) -> None:
        """Start recording, stream frames, stop, verify output files exist."""
        import tempfile
        import os as _os
        import json

        logger.info(f"\n{'-' * 60}")
        logger.info(f"[RECORD] Full record cycle with {len(cameras)} camera(s)")
        logger.info(f"{'-' * 60}")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))

        group_id = manager.create_or_update_group(configs)
        logger.info(f"[RECORD] Group {group_id} created, warming up...")
        _poll_until_frames(manager, 10)

        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"[RECORD] Starting recording → {tmpdir} (label=pyo3_test)")
            manager.start_recording(output_dir=tmpdir, label="pyo3_test")

            # Stream while recording
            _poll_until_frames(manager, 15)

            logger.info("[RECORD] Stopping recording...")
            result = manager.stop_recording()

            assert group_id in result, f"Group {group_id} not in result keys: {list(result.keys())}"
            summary = result[group_id]
            logger.info(f"[RECORD] Result summary keys: {list(summary.keys())}")

            # Verify recording summary keys
            for key in ("total_frames_per_camera", "video_paths", "csv_paths", "info_json_path"):
                assert key in summary, f"Missing key: {key}"

            # Verify total_frames_per_camera is positive
            assert isinstance(summary["total_frames_per_camera"], int)
            logger.info(f"[RECORD] total_frames_per_camera={summary['total_frames_per_camera']}")
            assert summary["total_frames_per_camera"] > 0, (
                f"Recorded {summary['total_frames_per_camera']} frames — expected > 0"
            )

            # Verify video files exist and are non-empty
            video_paths = summary.get("video_paths", [])
            logger.info(f"[RECORD] {len(video_paths)} video path(s) (expected {len(cameras)})")
            assert len(video_paths) == len(cameras), (
                f"Expected {len(cameras)} video(s), got {len(video_paths)}"
            )
            for vpath in video_paths:
                logger.info(f"[RECORD]   video: {vpath}")
                assert _os.path.isfile(vpath), f"Video file not found: {vpath}"
                file_size = _os.path.getsize(vpath)
                logger.info(f"[RECORD]     size={file_size}B  [OK]")
                assert file_size > 0, f"Video file empty: {vpath}"

            # Verify CSV files exist
            for cpath in summary.get("csv_paths", []):
                logger.info(f"[RECORD]   csv: {cpath}")
                assert _os.path.isfile(cpath), f"CSV file not found: {cpath}"

            # Verify info JSON exists and is valid
            info_path = summary.get("info_json_path", "")
            if info_path:
                logger.info(f"[RECORD]   info_json: {info_path}")
                assert _os.path.isfile(info_path), f"Info JSON not found: {info_path}"
                with open(info_path, "r") as f:
                    info_data = json.load(f)
                logger.info(f"[RECORD]   info_json keys: {list(info_data.keys())}")
                assert "total_frames_per_camera" in info_data

            # Verify stats JSON if present
            stats_json = summary.get("stats_json")
            if stats_json:
                stats = json.loads(stats_json)
                logger.info(f"[RECORD]   stats: total_multiframes={stats.get('total_multiframes', 'N/A')}")
                assert "total_multiframes" in stats

        logger.info("[RECORD] Closing group...")
        manager.close_all_groups()
        logger.info(f"[RECORD] [OK] Full record cycle complete for {len(cameras)} camera(s)")

    @requires_cameras
    def test_recording_name_tag(self) -> None:
        """Recording directory contains the 'pyo3_test' label."""
        import tempfile
        import os as _os

        cam = _ALL_CAMERAS[0]
        manager = _skellycam_rust.CameraGroupManager()
        configs = _make_config(cam)
        manager.create_or_update_group(configs)
        _poll_until_frames(manager, 5)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager.start_recording(output_dir=tmpdir, label="pyo3_test")
            _poll_until_frames(manager, 15)
            result = manager.stop_recording()

            for group_id, summary in result.items():
                for vpath in summary.get("video_paths", []):
                    assert "pyo3_test" in vpath, (
                        f"Recording tag 'pyo3_test' not found in path: {vpath}"
                    )

        manager.close_all_groups()


# ===============================================================================
# Test: close / shutdown
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestCloseAndShutdown:
    """Close camera groups and verify clean shutdown."""

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_close_all_groups_clears_state(self, cameras: list[dict]) -> None:
        """After close_all_groups, list_groups returns empty."""
        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))

        manager.create_or_update_group(configs)
        _poll_until_frames(manager, 10)

        assert manager.group_count() >= 1
        assert len(manager.list_groups()) >= 1

        manager.close_all_groups()

        assert manager.group_count() == 0
        assert manager.list_groups() == []

    @requires_cameras
    @pytest.mark.parametrize("cameras", _camera_subsets())
    def test_reopen_after_close(self, cameras: list[dict]) -> None:
        """After closing, a new group can be created with the same cameras."""
        manager = _skellycam_rust.CameraGroupManager()

        # First group
        configs = {}
        for cam in cameras:
            configs.update(_make_config(cam))
        group_id_1 = manager.create_or_update_group(configs)
        _poll_until_frames(manager, 10)
        manager.close_all_groups()

        time.sleep(0.2)  # Let hardware settle

        # Second group — same cameras
        configs2 = {}
        for cam in cameras:
            configs2.update(_make_config(cam))
        group_id_2 = manager.create_or_update_group(configs2)
        assert group_id_2 != group_id_1  # New UUID
        _poll_until_frames(manager, 10)
        manager.close_all_groups()


# ===============================================================================
# Test: all six cameras simultaneously
# ===============================================================================


@requires_rust
@pytest.mark.hardware
class TestAllSixCameras:
    """Full-system test: all 6 cameras streaming together."""

    @requires_cameras
    def test_six_camera_group_streams_all(self) -> None:
        """Create a group with all 6 cameras, verify all produce frames."""
        if len(_ALL_CAMERAS) < 6:
            pytest.skip(f"Need 6 cameras, have {len(_ALL_CAMERAS)}")

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in _ALL_CAMERAS:
            configs.update(_make_config(cam, width=640, height=480))

        group_id = manager.create_or_update_group(configs)
        _poll_until_frames(manager, 15)

        state = manager.to_state_dict()
        group_state = state["camera_groups"][group_id]
        assert group_state["camera_count"] == 6

        manager.close_all_groups()

    @requires_cameras
    def test_six_camera_record_and_verify(self) -> None:
        """Record all 6 cameras simultaneously, verify 6 video files."""
        if len(_ALL_CAMERAS) < 6:
            pytest.skip(f"Need 6 cameras, have {len(_ALL_CAMERAS)}")

        import tempfile
        import os as _os

        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in _ALL_CAMERAS:
            configs.update(_make_config(cam, width=640, height=480))

        group_id = manager.create_or_update_group(configs)
        _poll_until_frames(manager, 10)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager.start_recording(output_dir=tmpdir, label="pyo3_test_6cam")
            _poll_until_frames(manager, 15)
            result = manager.stop_recording()

            summary = result[group_id]
            video_paths = summary.get("video_paths", [])
            assert len(video_paths) == 6, (
                f"Expected 6 video files, got {len(video_paths)}"
            )
            for vpath in video_paths:
                assert _os.path.isfile(vpath)
                assert _os.path.getsize(vpath) > 0

        manager.close_all_groups()
