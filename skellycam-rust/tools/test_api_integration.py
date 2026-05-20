"""API-level integration tests — FastAPI + Rust backend + real cameras.

Spins up a FastAPI app with the real camera routes (no mocks), backed by
the Rust PyO3 camera engine. Hits every HTTP endpoint and validates
responses match the OpenAPI schemas.

Usage::

    uv run python skellycam-rust/tools/test_api_integration.py
"""

import os
import sys
import json
import time
import traceback
import multiprocessing
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0
SKIP = 0

def log(msg: str) -> None:
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
# Build the test FastAPI app
# ---------------------------------------------------------------------------

section("BUILDING TEST FASTAPI APP")

log("Importing FastAPI + routes...")

import asyncio
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import skellycam
from skellycam.api.routers import SKELLYCAM_ROUTERS
from skellycam.api.http.app.health import health_router
from skellycam.api.http.app.shutdown import shutdown_router
from skellycam.core.camera_group.camera_group_manager import (
    RustCameraGroupManager,
    get_or_create_camera_group_manager,
    _CAMERA_GROUP_MANAGER,
)

log("Resetting singleton manager...")
# Reset the singleton so a fresh one is created for this test
import skellycam.core.camera_group.camera_group_manager as cgm_module
cgm_module._CAMERA_GROUP_MANAGER = None

# Create app state
global_kill_flag = multiprocessing.Value("b", False)
worker_registry = MagicMock()
worker_registry.heartbeat_timestamp = multiprocessing.Value("d", 0.0)

# Build minimal app — skip the heavy lifespan (bytecode compile, telemetry)
app = FastAPI()
app.state.global_kill_flag = global_kill_flag
app.state.worker_registry = worker_registry

# Register routes same as real app
for router in [health_router, shutdown_router]:
    app.include_router(router)

prefix = f"/{skellycam.__package_name__}"
for router in SKELLYCAM_ROUTERS:
    app.include_router(router, prefix=prefix)

# The camera router calls get_or_create_camera_group_manager(request.app)
# which uses USE_RUST_BACKEND (True by default) to create RustCameraGroupManager.
# We need to ensure the singleton is created with our app.
# Patch get_or_create_camera_group_manager to force use of our app
from skellycam.api.http.cameras import camera_router as cr_module
import skellycam.api.websocket.websocket_connect as ws_module

original_get_manager = cgm_module.get_or_create_camera_group_manager

def _test_get_manager(app_param=None):
    """Drop-in that uses our test app's state."""
    global _CAMERA_GROUP_MANAGER
    if _CAMERA_GROUP_MANAGER is not None:
        return _CAMERA_GROUP_MANAGER
    _CAMERA_GROUP_MANAGER = RustCameraGroupManager(
        global_kill_flag=app.state.global_kill_flag,
        worker_registry=app.state.worker_registry,
    )
    return _CAMERA_GROUP_MANAGER

cgm_module.get_or_create_camera_group_manager = _test_get_manager

log("Test FastAPI app built successfully")
ok("App created with camera routes")


# ---------------------------------------------------------------------------
# Async test runner
# ---------------------------------------------------------------------------

async def run_api_tests():
    global PASS, FAIL, SKIP

    # Use ASGI transport to hit the app in-process
    transport = httpx.ASGITransport(app=app)
    base_url = f"http://test/{skellycam.__package_name__}"

    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:

        # ── Health check ──────────────────────────────────────────────────
        section("HEALTH CHECK")

        try:
            resp = await client.get("/health")
            sub(f"  Status: {resp.status_code}")
            check(resp.status_code == 200, f"Health returns 200 (got {resp.status_code})")
            data = resp.json()
            sub(f"  Response: {json.dumps(data)}")
            ok("Health endpoint")
        except Exception as e:
            fail(f"Health endpoint: {e}")
            traceback.print_exc()

        # ── Camera detection ──────────────────────────────────────────────
        section("CAMERA DETECTION (POST /camera/detect)")

        try:
            resp = await client.post("/camera/detect", params={"filter_virtual": True})
            check(resp.status_code == 200, f"Detect returns 200 (got {resp.status_code})")
            data = resp.json()
            sub(f"  Response keys: {list(data.keys())}")
            cameras = data.get("cameras", [])
            sub(f"  Cameras detected: {len(cameras)}")
            for cam in cameras:
                sub(f"    [{cam['index']}] {cam['name']}  id={cam['camera_id']}  "
                    f"formats={len(cam.get('formats', []))}")
            check(len(cameras) >= 1, f"At least 1 camera detected (got {len(cameras)})")
            check(len(cameras) == 6, f"6 cameras detected (got {len(cameras)})")

            # Verify each camera has expected keys
            for cam in cameras:
                for key in ("index", "name", "camera_id", "formats", "vendor_id", "product_id"):
                    check(key in cam, f"  Camera {cam.get('index', '?')} has '{key}'")

            ALL_CAMERAS = cameras
            ok("Camera detection")
        except Exception as e:
            fail(f"Camera detection: {e}")
            traceback.print_exc()
            ALL_CAMERAS = []

        if not ALL_CAMERAS:
            log("Cannot continue without cameras.")
            return

        # ── Apply camera group (1 camera) ─────────────────────────────────
        section("APPLY CAMERA GROUP (POST /camera/group/apply) — 1 camera")

        first_cam = ALL_CAMERAS[0]
        configs_1 = {
            first_cam["camera_id"]: {
                "camera_id": first_cam["camera_id"],
                "camera_index": first_cam["index"],
                "camera_name": first_cam["name"],
                "use_this_camera": True,
                "resolution": {"height": 720, "width": 1280},
                "color_channels": 3,
                "pixel_format": "RGB",
                "exposure_mode": "MANUAL",
                "exposure": -7,
                "framerate": -1.0,
                "rotation": -1,
                "capture_fourcc": "MJPG",
                "writer_fourcc": "X264",
            }
        }

        try:
            resp = await client.post(
                "/camera/group/apply",
                json={"camera_configs": configs_1},
            )
            check(resp.status_code == 200, f"Apply returns 200 (got {resp.status_code})")
            data = resp.json()
            sub(f"  Response keys: {list(data.keys())}")
            group_id = data.get("group_id", "")
            sub(f"  group_id: {group_id}")
            check(len(group_id) == 6, f"group_id is 6-char hex (got '{group_id}')")

            returned_configs = data.get("camera_configs", {})
            check(len(returned_configs) == 1, f"1 camera config returned (got {len(returned_configs)})")
            ok("Apply 1-camera group")
        except Exception as e:
            fail(f"Apply 1-camera group: {e}")
            traceback.print_exc()
            group_id = None

        # Wait for camera to stabilize and produce frames
        if group_id:
            sub("  Waiting for camera to stabilize (~2s)...")
            time.sleep(2.5)

        # ── Pause / Unpause ───────────────────────────────────────────────
        section("PAUSE / UNPAUSE (GET /camera/group/all/pause_unpause)")

        try:
            # First pause
            resp = await client.get("/camera/group/all/pause_unpause")
            sub(f"  Pause response status: {resp.status_code}")
            check(resp.status_code == 200, f"Pause returns 200 (got {resp.status_code})")

            # Unpause
            resp2 = await client.get("/camera/group/all/pause_unpause")
            sub(f"  Unpause response status: {resp2.status_code}")
            check(resp2.status_code == 200, f"Unpause returns 200 (got {resp2.status_code})")

            ok("Pause/unpause cycle")
        except Exception as e:
            fail(f"Pause/unpause: {e}")
            traceback.print_exc()

        time.sleep(0.3)

        # ── Apply camera group (2 cameras) ────────────────────────────────
        section("APPLY CAMERA GROUP — 2 cameras")

        if len(ALL_CAMERAS) >= 2:
            second_cam = ALL_CAMERAS[1]
            configs_2 = {}
            for cam in [first_cam, second_cam]:
                configs_2[cam["camera_id"]] = {
                    "camera_id": cam["camera_id"],
                    "camera_index": cam["index"],
                    "camera_name": cam["name"],
                    "use_this_camera": True,
                    "resolution": {"height": 720, "width": 1280},
                    "color_channels": 3,
                    "pixel_format": "RGB",
                    "exposure_mode": "MANUAL",
                    "exposure": -7,
                    "framerate": -1.0,
                    "rotation": -1,
                    "capture_fourcc": "MJPG",
                    "writer_fourcc": "X264",
                }

            try:
                resp = await client.post(
                    "/camera/group/apply",
                    json={"camera_configs": configs_2},
                )
                check(resp.status_code == 200, f"Apply 2-cam returns 200 (got {resp.status_code})")
                data = resp.json()
                group_id_2 = data.get("group_id", "")
                returned = data.get("camera_configs", {})
                check(len(returned) == 2, f"2 camera configs (got {len(returned)})")
                ok("Apply 2-camera group")
            except Exception as e:
                fail(f"Apply 2-camera group: {e}")
                traceback.print_exc()
                group_id_2 = group_id
        else:
            skip_test(f"Apply 2-camera group (need 2+, have {len(ALL_CAMERAS)})")

        time.sleep(2.5)

        # ── Apply camera group (4 cameras) ────────────────────────────────
        section("APPLY CAMERA GROUP — 4 cameras")

        if len(ALL_CAMERAS) >= 4:
            configs_4 = {}
            for cam in ALL_CAMERAS[:4]:
                configs_4[cam["camera_id"]] = {
                    "camera_id": cam["camera_id"],
                    "camera_index": cam["index"],
                    "camera_name": cam["name"],
                    "use_this_camera": True,
                    "resolution": {"height": 720, "width": 1280},
                    "color_channels": 3,
                    "pixel_format": "RGB",
                    "exposure_mode": "MANUAL",
                    "exposure": -7,
                    "framerate": -1.0,
                    "rotation": -1,
                    "capture_fourcc": "MJPG",
                    "writer_fourcc": "X264",
                }

            try:
                resp = await client.post(
                    "/camera/group/apply",
                    json={"camera_configs": configs_4},
                )
                check(resp.status_code == 200, f"Apply 4-cam returns 200 (got {resp.status_code})")
                data = resp.json()
                group_id_4 = data.get("group_id", "")
                returned = data.get("camera_configs", {})
                check(len(returned) == 4, f"4 camera configs (got {len(returned)})")
                ok("Apply 4-camera group")
            except Exception as e:
                fail(f"Apply 4-camera group: {e}")
                traceback.print_exc()
        else:
            skip_test(f"Apply 4-camera group (need 4+, have {len(ALL_CAMERAS)})")

        time.sleep(2.5)

        # ── Start recording ───────────────────────────────────────────────
        section("START RECORDING (POST /camera/group/all/record/start)")

        import tempfile
        tmpdir = tempfile.mkdtemp(prefix="skellycam_api_test_")
        sub(f"  Record dir: {tmpdir}")

        try:
            resp = await client.post(
                "/camera/group/all/record/start",
                json={
                    "recording_name": "api_test_recording",
                    "recording_directory": tmpdir,
                    "mic_device_index": -1,
                },
            )
            check(resp.status_code == 200, f"Start recording returns 200 (got {resp.status_code})")
            sub(f"  Response: {resp.json()}")
            ok("Start recording")
        except Exception as e:
            fail(f"Start recording: {e}")
            traceback.print_exc()

        # Let it record for a bit
        sub("  Recording for 3 seconds...")
        time.sleep(3.0)

        # ── Stop recording ────────────────────────────────────────────────
        section("STOP RECORDING (GET /camera/group/all/record/stop)")

        try:
            resp = await client.get("/camera/group/all/record/stop")
            check(resp.status_code == 200, f"Stop recording returns 200 (got {resp.status_code})")
            data = resp.json()
            sub(f"  Response type: {type(data)}  len={len(data)}")
            check(isinstance(data, list), f"Response is a list (got {type(data).__name__})")

            if isinstance(data, list) and len(data) > 0:
                result = data[0]
                required_keys = [
                    "recording_name", "recording_path", "number_of_cameras",
                    "number_of_frames", "total_duration_sec", "mean_framerate",
                    "mean_inter_camera_sync_ms", "framerate_stats",
                    "frame_duration_stats", "inter_camera_grab_range_ms_stats",
                ]
                sub(f"  Response keys: {list(result.keys())}")
                for key in required_keys:
                    check(key in result, f"StopRecordingResponse has '{key}'")

                # Verify nested StatsSummary
                for stats_key in ("framerate_stats", "frame_duration_stats",
                                   "inter_camera_grab_range_ms_stats"):
                    stats = result.get(stats_key, {})
                    for stat_field in ("median", "mean", "std", "min", "max"):
                        check(stat_field in stats,
                              f"  {stats_key}.{stat_field} present")

                check(result["number_of_frames"] > 0,
                      f"number_of_frames > 0 ({result.get('number_of_frames', 0)})")

                # Verify video files exist
                rec_path = result.get("recording_path", "")
                if rec_path and os.path.isdir(rec_path):
                    videos_dir = os.path.join(rec_path, "synchronized_videos")
                    if os.path.isdir(videos_dir):
                        mp4s = [f for f in os.listdir(videos_dir) if f.endswith(".mp4")]
                        sub(f"  MP4 files found: {len(mp4s)}")
                        for mp4 in mp4s[:3]:
                            fpath = os.path.join(videos_dir, mp4)
                            fsize = os.path.getsize(fpath)
                            sub(f"    {mp4}: {fsize}B")
                    else:
                        sub(f"  videos_dir not found: {videos_dir}")
                else:
                    sub(f"  recording_path: {rec_path}")

            ok("Stop recording")
        except Exception as e:
            fail(f"Stop recording: {e}")
            traceback.print_exc()

        # ── Close all groups ──────────────────────────────────────────────
        section("CLOSE ALL GROUPS (DELETE /camera/group/close/all)")

        try:
            resp = await client.delete("/camera/group/close/all")
            check(resp.status_code == 200, f"Close all returns 200 (got {resp.status_code})")
            sub(f"  Response: {resp.json()}")
            ok("Close all groups")
        except Exception as e:
            fail(f"Close all groups: {e}")
            traceback.print_exc()

        # Clean up temp dir
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

        # ── Reopen after close ────────────────────────────────────────────
        section("REOPEN AFTER CLOSE")

        try:
            # Reset singleton to force fresh manager
            cgm_module._CAMERA_GROUP_MANAGER = None

            configs_reopen = {}
            for cam in ALL_CAMERAS[:2]:
                configs_reopen[cam["camera_id"]] = {
                    "camera_id": cam["camera_id"],
                    "camera_index": cam["index"],
                    "camera_name": cam["name"],
                    "use_this_camera": True,
                    "resolution": {"height": 480, "width": 640},
                    "color_channels": 3,
                    "pixel_format": "RGB",
                    "exposure_mode": "MANUAL",
                    "exposure": -7,
                    "framerate": -1.0,
                    "rotation": -1,
                    "capture_fourcc": "MJPG",
                    "writer_fourcc": "X264",
                }

            resp = await client.post(
                "/camera/group/apply",
                json={"camera_configs": configs_reopen},
            )
            check(resp.status_code == 200, f"Reopen returns 200 (got {resp.status_code})")
            data = resp.json()
            new_group_id = data.get("group_id", "")
            check(len(new_group_id) == 6, f"Reopen group_id is valid ({new_group_id})")

            # Let it stream briefly
            sub("  Streaming for 2s after reopen...")
            time.sleep(2.5)

            # Close again
            resp2 = await client.delete("/camera/group/close/all")
            check(resp2.status_code == 200, f"Close after reopen returns 200")
            ok("Reopen after close")
        except Exception as e:
            fail(f"Reopen after close: {e}")
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    section("API INTEGRATION TESTS")
    log(f"  skellycam version: {skellycam.__version__}")
    log(f"  Rust backend: USE_RUST_BACKEND={cgm_module.USE_RUST_BACKEND}")

    asyncio.run(run_api_tests())

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


if __name__ == "__main__":
    main()
