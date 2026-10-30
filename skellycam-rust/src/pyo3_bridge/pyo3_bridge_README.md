# PyO3 Bridge Module

Python bindings for the Rust camera engine. Exposes `CameraGroupManager` (the Python
class name; the Rust struct is `PyO3CameraGroupManager`) and supporting types as a
Python module (`_skellycam_rust`). This is a thin adapter — all camera logic lives in
the pure Rust modules underneath.

## Architecture

```
┌─ Python layer ─────────────────────────────────────────────────┐
│  skellycam.core.camera_group.camera_group_manager               │
│    │                                                            │
│    │ import _skellycam_rust                                      │
│    ▼                                                            │
├─ PyO3 bridge ──────────────────────────────────────────────────┤
│  PyO3CameraGroupManager (py_camera_group_manager.rs)            │
│    - Parses Python dicts → CameraGroupConfig                    │
│    - Owns HashMap<String, Mutex<CameraGroup>>                   │
│    - Polls CameraGroup::latest_frontend_payload() for frames    │
│    - Delegates recording to CameraGroup                         │
│    │                                                            │
│  Data types (types.rs)                                          │
│    ImageResolution, CameraConfig, RecordingInfo, etc.           │
│    │                                                            │
│  detect_cameras() (mod.rs)                                      │
│    Free function: detects cameras, returns Python dicts          │
├─ Pure Rust layer ──────────────────────────────────────────────┤
│  camera_group::CameraGroup                                      │
│    Spawns its own dispatcher thread for frontend encoding        │
│  camera::Camera                                                 │
└────────────────────────────────────────────────────────────────┘
```

## Thread Model

```
Camera threads (N) ── frame ──→ Gatherer thread ── multiframe ──→ Dispatcher thread
       │         barrier(N+1)    │    barrier(N+1)     │                    │
       └───────────┴─────────────┘                      │                    │
                                              Encodes JPEG payload        Recording
                                              → Arc<Mutex<Option<...>>>   (ffmpeg+CSV)
                                                        │
                           Python asyncio polls ←───────┘
                           get_latest_frame_payloads()
```

The dispatcher thread is spawned by `CameraGroup::start()`, not by the PyO3 bridge.
It encodes every multiframe into a JPEG payload stored in a shared
`Arc<Mutex<Option<FrontendPayload>>>`. Python polls `get_latest_frame_payloads()` on
each asyncio iteration (~10ms) — no GIL is held during encoding, only during the
brief lock to read the latest payload.

## Public Python API

```python
import _skellycam_rust

# Detection
cameras = _skellycam_rust.detect_cameras()  # → list[dict]

# Group management (supports multiple concurrent groups)
manager = _skellycam_rust.CameraGroupManager()
group_id = manager.create_or_update_group(camera_configs_dict)

# Frame polling (called from asyncio)
payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
# → dict[group_id: (frame_number, timestamp_ns, jpeg_bytes)]

# Recording
manager.start_recording(output_dir="/path/to/recordings", label="session_1")
# ... frames accumulate on the dispatcher thread ...
summary = manager.stop_recording()  # → dict[group_id: RecordingSummary]

# Config updates (add/remove/reconfigure cameras on a running group)
manager.apply_configs(group_id, updated_configs_dict)

# Teardown
manager.close_all_groups()
```

## Files

| File | Purpose |
|---|---|
| `mod.rs` | Python module init (`_skellycam_rust`), `detect_cameras()` pyfunction |
| `py_camera_group_manager.rs` | `PyO3CameraGroupManager` pyclass — group lifecycle + frame polling |
| `types.rs` | Python-facing dataclass equivalents (`ImageResolution`, `CameraConfig`, etc.) |

## Design Decisions

**Thin adapter.** The PyO3 bridge converts Python types to Rust types, delegates to
pure Rust modules, and converts results back. This keeps the Rust code testable
without a Python interpreter.

**Dispatcher thread, not GIL.** JPEG encoding runs on the dispatcher thread (spawned
by `CameraGroup::start()`) without the Python GIL. Python only locks briefly to swap
the latest payload. This prevents the camera pipeline from being blocked by Python
garbage collection or slow asyncio loop iterations.

**Multiple groups.** `PyO3CameraGroupManager` stores groups in a
`HashMap<String, Mutex<CameraGroup>>`. Multiple groups can run concurrently. Methods
that target "all groups" (pause, unpause, start_recording, stop_recording) iterate
over all entries.

**Python dict → Rust config.** Config fields are parsed from Python dicts using
`getattr` / `get_item` fallbacks, matching both object-attribute and dict-key
access patterns. Missing fields get sensible defaults (1280×720, exposure=-7,
exposure_mode="MANUAL").

## Build

```bash
cargo build --release
```
