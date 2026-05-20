"""Comprehensive PyO3 bridge hardware test — standalone, no pytest.

Tests every camera operation through the PyO3 bridge against real hardware.
Mirrors the Rust test suite in ``skellycam-rust/src/tests/all_tests.rs``.

Usage::

    uv run python skellycam-rust/tools/test_pyo3_bridge_hardware.py
"""

import os
import sys
import json
import time
import tempfile
import traceback

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0
SKIP = 0

def log(msg: str) -> None:
    """Print immediately with flush so we can see progress in real time."""
    print(msg, flush=True)

def section(title: str) -> None:
    log("")
    log("=" * 78)
    log(f"  {title}")
    log("=" * 78)

def sub(msg: str) -> None:
    log(f"  {msg}")

def ok(msg: str) -> None:
    global PASS
    PASS += 1
    log(f"  [OK] {msg}")

def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    log(f"  [FAIL] {msg}")

def skip_test(msg: str) -> None:
    global SKIP
    SKIP += 1
    log(f"  [SKIP] {msg}")

def check(condition: bool, msg: str) -> None:
    if condition:
        ok(msg)
    else:
        fail(msg)

# ---------------------------------------------------------------------------
# Import and detection
# ---------------------------------------------------------------------------

section("IMPORT AND CAMERA DETECTION")

log("Importing _skellycam_rust...")
try:
    import _skellycam_rust
    ok("_skellycam_rust imported")
except ImportError as e:
    fail(f"_skellycam_rust not available: {e}")
    log("Cannot continue without Rust extension. Run: uv run poe rebuild")
    sys.exit(1)

log("Detecting cameras via Rust openpnp-capture engine...")
try:
    ALL_CAMERAS = _skellycam_rust.detect_cameras()
    sub(f"Detected {len(ALL_CAMERAS)} camera(s) (after filtering virtual/no-MJPG)")
    for cam in ALL_CAMERAS:
        sub(f"  [{cam['camera_index']}] id={cam['unique_identifier']}  "
            f"name=\"{cam['display_name']}\"  formats={len(cam.get('formats', []))}")
except Exception as e:
    fail(f"Camera detection failed: {e}")
    traceback.print_exc()
    sys.exit(1)

check(len(ALL_CAMERAS) >= 1, f"At least 1 camera detected (got {len(ALL_CAMERAS)})")

# Check all cameras have MJPG
for cam in ALL_CAMERAS:
    fourccs = {fmt["fourcc_str"] for fmt in cam.get("formats", [])}
    check("MJPG" in fourccs, f"Camera {cam['camera_index']} ({cam['unique_identifier']}) has MJPG format")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(camera: dict, **overrides) -> dict:
    """Build a config dict matching the HTTP /group/apply endpoint body."""
    cfg = {
        "camera_id": camera["unique_identifier"],
        "camera_index": camera["camera_index"],
        "width": overrides.get("width", 1280),
        "height": overrides.get("height", 720),
        "exposure": overrides.get("exposure", -7),
        "exposure_mode": overrides.get("exposure_mode", "MANUAL"),
        "framerate": overrides.get("framerate", -1.0),
        "rotation": overrides.get("rotation", -1),
    }
    return {cfg["camera_id"]: cfg}


def poll_until_frames(manager, target_count: int, timeout_secs: float = 30.0) -> int:
    """Poll until target_count frames arrive. Returns last frame number.

    Validates BOTH PyO3 routes:
    1. get_latest_frame_payloads() — wire-format frontend binary
    2. get_latest_raw_frames() — raw per-camera MJPEG bytes
    """
    start = time.monotonic()
    last_frame = -1
    count = 0

    while count < target_count:
        payloads = manager.get_latest_frame_payloads(if_newer_than=last_frame)
        for _group_id, (frame_number, _timestamp_ns, payload_bytes) in payloads.items():
            if frame_number > last_frame:
                last_frame = int(frame_number)
                count += 1
                # Wire-format validation
                wire_ok = _validate_wire_format(payload_bytes)
                if not wire_ok:
                    raise AssertionError(
                        f"Frame {frame_number}: invalid wire-format payload "
                        f"(len={len(payload_bytes)}, first 4 bytes: {payload_bytes[:4]!r})"
                    )

                if count <= 5 or count % 10 == 0:
                    elapsed = time.monotonic() - start
                    sub(f"  frame#{frame_number:>4d}  payload={len(payload_bytes):>6d}B  "
                        f"count={count}/{target_count}  elapsed={elapsed:.1f}s")

        if time.monotonic() - start > timeout_secs:
            elapsed = time.monotonic() - start
            raise TimeoutError(
                f"Timed out after {elapsed:.1f}s — got {count}/{target_count} frames"
            )
        time.sleep(0.001)

    elapsed = time.monotonic() - start
    sub(f"  Done: {count} frames in {elapsed:.1f}s ({count / elapsed:.1f} fps Python-side)")

    # Validate raw JPEG route
    raw_frames = manager.get_latest_raw_frames()
    for group_id, camera_frames in raw_frames.items():
        for camera_id, frame_info in camera_frames.items():
            jpeg_bytes = frame_info["jpeg_bytes"]
            w, h = frame_info["width"], frame_info["height"]
            so1, so2 = jpeg_bytes[:2]
            if so1 != 0xFF or so2 != 0xD8:
                raise AssertionError(
                    f"Camera {camera_id}: raw JPEG missing SOI marker "
                    f"(expected FF D8, got {so1:02X} {so2:02X})"
                )
            sub(f"  raw: cam={camera_id}  {w}x{h}  {len(jpeg_bytes):>6d}B  "
                f"SOI=[{so1:02X} {so2:02X}]  valid JPEG")

    return last_frame


def _validate_wire_format(payload_bytes: bytes) -> bool:
    """Validate frontend wire-format binary (PayloadHeader + FrameHeaders + JPEGs + Footer)."""
    if len(payload_bytes) < 104:
        return False
    if payload_bytes[0] != 0:  # PayloadHeader.message_type
        return False

    offset = 24  # Past PayloadHeader
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


# ---------------------------------------------------------------------------
# Test: Connect and stream (1, 2, 4, 6 cameras)
# ---------------------------------------------------------------------------

section("CONNECT AND STREAM")

CAMERA_COUNTS = [n for n in [1, 2, 4, 6] if n <= len(ALL_CAMERAS)]

for num_cameras in CAMERA_COUNTS:
    cameras = ALL_CAMERAS[:num_cameras]
    sub(f"-- {num_cameras} camera(s) --")

    try:
        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(make_config(cam))

        group_id = manager.create_or_update_group(configs)
        sub(f"  group_id={group_id}")

        poll_until_frames(manager, 15)
        manager.close_all_groups()
        ok(f"Connect+stream with {num_cameras} camera(s)")
    except Exception as e:
        fail(f"Connect+stream with {num_cameras} camera(s): {e}")
        traceback.print_exc()
        try:
            manager.close_all_groups()
        except Exception:
            pass

    time.sleep(0.2)  # Let hardware settle between tests


# ---------------------------------------------------------------------------
# Test: Pause / Unpause
# ---------------------------------------------------------------------------

section("PAUSE / UNPAUSE")

cam = ALL_CAMERAS[0]
try:
    manager = _skellycam_rust.CameraGroupManager()
    configs = make_config(cam)
    manager.create_or_update_group(configs)
    poll_until_frames(manager, 10)

    # Get current frame number
    payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
    before = 0
    for _gid, (fn, _ts, _jpeg) in payloads.items():
        before = int(fn)
    sub(f"  Frame before pause: {before}")

    # Pause
    manager.pause()
    sub("  Paused, waiting 0.5s...")
    time.sleep(0.5)

    # Check frame hasn't advanced
    payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
    during = before
    for _gid, (fn, _ts, _jpeg) in payloads.items():
        during = int(fn)
    sub(f"  Frame during pause: {during}")
    check(during == before, f"Frame did not advance during pause (was {before}, still {during})")

    # Unpause
    manager.unpause()
    sub("  Unpaused...")
    poll_until_frames(manager, 5)

    # Verify frames resumed
    payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
    after = before
    for _gid, (fn, _ts, _jpeg) in payloads.items():
        after = int(fn)
    check(after > before, f"Frame advanced after unpause (was {before}, now {after})")

    manager.close_all_groups()
    ok("Pause/unpause cycle")
except Exception as e:
    fail(f"Pause/unpause: {e}")
    traceback.print_exc()
    try:
        manager.close_all_groups()
    except Exception:
        pass

time.sleep(0.2)


# ---------------------------------------------------------------------------
# Test: Exposure
# ---------------------------------------------------------------------------

section("EXPOSURE UPDATE")

try:
    manager = _skellycam_rust.CameraGroupManager()
    configs = make_config(cam, exposure=-7)
    group_id = manager.create_or_update_group(configs)
    poll_until_frames(manager, 10)

    # Change to brighter
    sub("Changing exposure: -7 -> -4")
    updated = make_config(cam, exposure=-4)
    manager.apply_configs(group_id, updated)
    poll_until_frames(manager, 10)
    ok("Exposure changed to -4, frames still flowing")

    # Change to darker
    sub("Changing exposure: -4 -> -10")
    updated2 = make_config(cam, exposure=-10)
    manager.apply_configs(group_id, updated2)
    poll_until_frames(manager, 10)
    ok("Exposure changed to -10, frames still flowing")

    manager.close_all_groups()
except Exception as e:
    fail(f"Exposure update: {e}")
    traceback.print_exc()
    try:
        manager.close_all_groups()
    except Exception:
        pass

time.sleep(0.2)


# ---------------------------------------------------------------------------
# Test: Rotation
# ---------------------------------------------------------------------------

section("ROTATION (-1, 0, 1, 2)")

ROTATION_NAMES = {-1: "NO_ROTATION", 0: "CW_90", 1: "ROTATE_180", 2: "CCW_90"}

for rotation in [-1, 0, 1, 2]:
    try:
        sub(f"Testing rotation={rotation} ({ROTATION_NAMES[rotation]})")
        manager = _skellycam_rust.CameraGroupManager()
        configs = make_config(cam, width=640, height=480, rotation=rotation)
        manager.create_or_update_group(configs)
        poll_until_frames(manager, 10)
        manager.close_all_groups()
        ok(f"Rotation {rotation} ({ROTATION_NAMES[rotation]})")
    except Exception as e:
        fail(f"Rotation {rotation}: {e}")
        traceback.print_exc()
        try:
            manager.close_all_groups()
        except Exception:
            pass

    time.sleep(0.15)


# ---------------------------------------------------------------------------
# Test: Framerate
# ---------------------------------------------------------------------------

section("FRAMERATE")

# 30fps
try:
    sub("Testing framerate=30fps")
    manager = _skellycam_rust.CameraGroupManager()
    configs = make_config(cam, framerate=30.0)
    manager.create_or_update_group(configs)

    # Wait for first frame to establish baseline (excludes stabilization)
    start_total = time.monotonic()
    last_fn = -1
    first_frame_time = None
    while time.monotonic() - start_total < 30:
        payloads = manager.get_latest_frame_payloads(if_newer_than=last_fn)
        for _gid, (fn, _ts, _jpeg) in payloads.items():
            if fn > last_fn:
                last_fn = int(fn)
                if first_frame_time is None:
                    first_frame_time = time.monotonic()
        if last_fn >= 0:
            break
        time.sleep(0.001)

    # Now measure FPS from first frame
    count = 0
    while count < 15:
        payloads = manager.get_latest_frame_payloads(if_newer_than=last_fn)
        for _gid, (fn, _ts, _jpeg) in payloads.items():
            if fn > last_fn:
                last_fn = int(fn)
                count += 1
                if count == 1:
                    measure_start = time.monotonic()
        if time.monotonic() - start_total > 30:
            raise TimeoutError(f"Timed out — got {count} frames")
        time.sleep(0.001)

    measure_elapsed = time.monotonic() - measure_start
    measure_fps = 15 / measure_elapsed
    sub(f"  Measured: {measure_fps:.1f} fps (requested 30, {15} frames in {measure_elapsed:.1f}s post-stabilization)")
    check(measure_fps >= 15.0, f"30fps setting yields >=15fps actual (got {measure_fps:.1f})")
    manager.close_all_groups()
    ok("Framerate 30fps")
except Exception as e:
    fail(f"Framerate 30fps: {e}")
    traceback.print_exc()
    try:
        manager.close_all_groups()
    except Exception:
        pass

time.sleep(0.2)

# Default framerate
try:
    sub("Testing framerate=-1 (camera default)")
    manager = _skellycam_rust.CameraGroupManager()
    configs = make_config(cam, framerate=-1.0)
    manager.create_or_update_group(configs)
    poll_until_frames(manager, 15)
    manager.close_all_groups()
    ok("Default framerate")
except Exception as e:
    fail(f"Default framerate: {e}")
    traceback.print_exc()
    try:
        manager.close_all_groups()
    except Exception:
        pass

time.sleep(0.2)


# ---------------------------------------------------------------------------
# Test: Resolution
# ---------------------------------------------------------------------------

section("RESOLUTION")

RESOLUTIONS = [(1920, 1080), (1280, 720), (640, 480)]

for width, height in RESOLUTIONS:
    try:
        sub(f"Testing {width}x{height}")
        manager = _skellycam_rust.CameraGroupManager()
        configs = make_config(cam, width=width, height=height)
        manager.create_or_update_group(configs)
        poll_until_frames(manager, 10)

        raw_frames = manager.get_latest_raw_frames()
        for group_id, camera_frames in raw_frames.items():
            for camera_id, frame_info in camera_frames.items():
                rw, rh = frame_info["width"], frame_info["height"]
                sub(f"  raw frame: {rw}x{rh} (requested {width}x{height})")
                jpeg_size = len(frame_info["jpeg_bytes"])
                sub(f"  JPEG size: {jpeg_size}B")
                if width >= 1920:
                    check(jpeg_size > 10000, f"1080p JPEG size {jpeg_size}B > 10000B")
                elif width <= 640:
                    check(jpeg_size < 200000, f"480p JPEG size {jpeg_size}B < 200000B")

        manager.close_all_groups()
        ok(f"Resolution {width}x{height}")
    except Exception as e:
        fail(f"Resolution {width}x{height}: {e}")
        traceback.print_exc()
        try:
            manager.close_all_groups()
        except Exception:
            pass

    time.sleep(0.15)


# ---------------------------------------------------------------------------
# Test: Add / Remove Cameras
# ---------------------------------------------------------------------------

section("ADD / REMOVE CAMERAS")

if len(ALL_CAMERAS) >= 2:
    try:
        # Start with 1 camera
        sub("Starting with 1 camera, then adding a second...")
        manager = _skellycam_rust.CameraGroupManager()
        configs = make_config(ALL_CAMERAS[0])
        group_id = manager.create_or_update_group(configs)
        poll_until_frames(manager, 10)

        # Add second camera
        updated = {}
        updated.update(make_config(ALL_CAMERAS[0]))
        updated.update(make_config(ALL_CAMERAS[1]))
        sub(f"  Adding camera {ALL_CAMERAS[1]['camera_index']} ({ALL_CAMERAS[1]['unique_identifier']})")
        manager.apply_configs(group_id, updated)
        poll_until_frames(manager, 10)

        state = manager.to_state_dict()
        cam_count = state["camera_groups"][group_id]["camera_count"]
        check(cam_count == 2, f"After add: camera_count={cam_count} (expected 2)")

        # Remove second camera
        sub("  Removing second camera...")
        manager.apply_configs(group_id, make_config(ALL_CAMERAS[0]))
        poll_until_frames(manager, 10)

        state = manager.to_state_dict()
        cam_count = state["camera_groups"][group_id]["camera_count"]
        check(cam_count == 1, f"After remove: camera_count={cam_count} (expected 1)")

        manager.close_all_groups()
        ok("Add/remove cameras")
    except Exception as e:
        fail(f"Add/remove cameras: {e}")
        traceback.print_exc()
        try:
            manager.close_all_groups()
        except Exception:
            pass
else:
    skip_test(f"Add/remove cameras (need 2+, have {len(ALL_CAMERAS)})")

time.sleep(0.2)


# ---------------------------------------------------------------------------
# Test: Recording (1, 2, 4, 6 cameras)
# ---------------------------------------------------------------------------

section("RECORDING (pyo3_test tag)")

for num_cameras in CAMERA_COUNTS:
    cameras = ALL_CAMERAS[:num_cameras]

    try:
        sub(f"-- Recording with {num_cameras} camera(s) --")
        manager = _skellycam_rust.CameraGroupManager()
        configs = {}
        for cam in cameras:
            configs.update(make_config(cam))

        group_id = manager.create_or_update_group(configs)
        poll_until_frames(manager, 10)

        with tempfile.TemporaryDirectory() as tmpdir:
            sub(f"  Output dir: {tmpdir}")
            manager.start_recording(output_dir=tmpdir, label="pyo3_test")

            poll_until_frames(manager, 15)

            sub("  Stopping recording...")
            result = manager.stop_recording()

            # Verify result structure
            sub(f"  Result groups: {list(result.keys())}")
            summary = result.get(group_id, {})

            check("total_frames_per_camera" in summary,
                  f"total_frames_per_camera in summary ({summary.get('total_frames_per_camera', 'N/A')})")
            check(int(summary.get("total_frames_per_camera", 0)) > 0,
                  f"total_frames_per_camera > 0 ({summary.get('total_frames_per_camera', 0)})")

            video_paths = summary.get("video_paths", [])
            sub(f"  Video paths: {len(video_paths)}")
            for vpath in video_paths:
                sub(f"    {vpath}")
                if os.path.isfile(vpath):
                    size = os.path.getsize(vpath)
                    sub(f"      size={size}B")
                    check(size > 0, f"Video file non-empty: {vpath}")
                else:
                    fail(f"Video file missing: {vpath}")

            csv_paths = summary.get("csv_paths", [])
            for cpath in csv_paths:
                check(os.path.isfile(cpath), f"CSV exists: {cpath}")

            info_path = summary.get("info_json_path", "")
            if info_path and os.path.isfile(info_path):
                with open(info_path) as f:
                    info = json.load(f)
                sub(f"  Recording info: {list(info.keys())}")
                check("total_frames_per_camera" in info, "Info JSON has total_frames_per_camera")

            stats_json = summary.get("stats_json")
            if stats_json:
                stats = json.loads(stats_json)
                sub(f"  Stats: total_multiframes={stats.get('total_multiframes', 'N/A')}")
                check("total_multiframes" in stats, "Stats JSON has total_multiframes")

        manager.close_all_groups()
        ok(f"Recording with {num_cameras} camera(s)")
    except Exception as e:
        fail(f"Recording with {num_cameras} camera(s): {e}")
        traceback.print_exc()
        try:
            manager.close_all_groups()
        except Exception:
            pass

    time.sleep(0.3)


# ---------------------------------------------------------------------------
# Test: Close and reopen
# ---------------------------------------------------------------------------

section("CLOSE AND REOPEN")

try:
    sub("Creating first group...")
    manager = _skellycam_rust.CameraGroupManager()
    configs = make_config(cam)
    group_id_1 = manager.create_or_update_group(configs)
    poll_until_frames(manager, 10)

    check(manager.group_count() >= 1, f"Groups before close: {manager.group_count()}")

    sub("Closing all groups...")
    manager.close_all_groups()
    check(manager.group_count() == 0, f"Groups after close: {manager.group_count()}")
    check(manager.list_groups() == [], f"list_groups() empty after close")

    time.sleep(0.2)

    sub("Creating second group (reopen)...")
    configs2 = make_config(cam)
    group_id_2 = manager.create_or_update_group(configs2)
    sub(f"  New group_id: {group_id_2} (previous: {group_id_1})")
    check(group_id_2 != group_id_1, f"New group has different ID: {group_id_2} != {group_id_1}")

    poll_until_frames(manager, 10)
    manager.close_all_groups()
    ok("Close and reopen")
except Exception as e:
    fail(f"Close and reopen: {e}")
    traceback.print_exc()
    try:
        manager.close_all_groups()
    except Exception:
        pass

time.sleep(0.2)


# ---------------------------------------------------------------------------
# Test: All 6 cameras
# ---------------------------------------------------------------------------

section("ALL 6 CAMERAS SIMULTANEOUSLY")

try:
    sub("Creating group with all 6 cameras at 640x480...")
    manager = _skellycam_rust.CameraGroupManager()
    configs = {}
    for cam in ALL_CAMERAS:
        configs.update(make_config(cam, width=640, height=480))

    group_id = manager.create_or_update_group(configs)
    poll_until_frames(manager, 15)

    state = manager.to_state_dict()
    cam_count = state["camera_groups"][group_id]["camera_count"]
    check(cam_count == 6, f"6-camera group: camera_count={cam_count}")

    # Record all 6
    sub("Recording all 6 cameras...")
    with tempfile.TemporaryDirectory() as tmpdir:
        manager.start_recording(output_dir=tmpdir, label="pyo3_test_6cam")
        poll_until_frames(manager, 15)
        result = manager.stop_recording()

        summary = result.get(group_id, {})
        video_paths = summary.get("video_paths", [])
        sub(f"  {len(video_paths)} video files")
        for vpath in video_paths:
            sub(f"    {vpath}")
            check(os.path.isfile(vpath), f"Video exists: {vpath}")
            check(os.path.getsize(vpath) > 0, f"Video non-empty: {vpath}")
        check(len(video_paths) == 6, f"6 video files (got {len(video_paths)})")

    manager.close_all_groups()
    ok("All 6 cameras simultaneous record")
except Exception as e:
    fail(f"All 6 cameras: {e}")
    traceback.print_exc()
    try:
        manager.close_all_groups()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

section("SUMMARY")

total = PASS + FAIL + SKIP
log(f"  Passed:  {PASS}/{total}")
log(f"  Failed:  {FAIL}/{total}")
log(f"  Skipped: {SKIP}/{total}")
log("")

if FAIL > 0:
    log(f"  {FAIL} TEST(S) FAILED!")
    sys.exit(1)
else:
    log("  ALL TESTS PASSED")
    sys.exit(0)
