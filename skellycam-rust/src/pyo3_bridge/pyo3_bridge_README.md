# PyO3 Bridge Module

Python bindings for the Rust camera engine. Exposes `PyO3CameraGroupManager` and
supporting types as a Python module (`_skellycam_rust`). This is a thin adapter —
all camera logic lives in the pure Rust modules underneath.

## Architecture

```
┌─ Python layer ─────────────────────────────────────────────┐
│  skellycam.core.camera_group.camera_group_manager           │
│    │                                                        │
│    │ import _skellycam_rust                                  │
│    ▼                                                        │
├─ PyO3 bridge ──────────────────────────────────────────────┤
│  PyO3CameraGroupManager (py_camera_group_manager.rs)        │
│    - Parses Python dicts → CameraGroupConfig                │
│    - Creates CameraGroup, extracts receiver                  │
│    - Spawns pipeline thread for JPEG encoding                │
│    - Provides get_latest_frame_payloads() for async polling  │
│    │                                                        │
│  Data types (types.rs)                                      │
│    ImageResolution, CameraConfig, RecordingInfo, etc.        │
│    │                                                        │
│  detect_cameras() (mod.rs)                                  │
│    Free function: detects cameras, returns Python dicts      │
├─ Pure Rust layer ──────────────────────────────────────────┤
│  camera_group_manager::CameraGroupManager                    │
│  camera_group::CameraGroup                                   │
│  camera::Camera                                              │
└────────────────────────────────────────────────────────────┘
```

## Thread Model

```
Camera threads (N) ── frame ──→ Gatherer thread ── multiframe ──→ Pipeline thread
                                      │                                  │
                                      │ barrier                         │ JPEG encode
                                      │                                  │
                              Camera threads                       Arc<Mutex<Option<...>>>
                              wait at barrier                            │
                                                                         │
                                                Python asyncio polls ←──┘
                                                get_latest_frame_payloads()
```

The pipeline thread owns the `CameraGroup`, takes its multiframe receiver via
`take_multiframe_receiver()`, and runs `consume_multiframe_loop`. Each multiframe
is JPEG-encoded via `frontend_payload::encode_multiframe()` and stored in a
shared `Arc<Mutex<Option<(frame_number, timestamp_ns, jpeg_bytes)>>>`.

Python polls `get_latest_frame_payloads()` on each asyncio iteration (~10ms).
When `close_all_groups()` is called, the running flag is cleared, the pipeline
thread exits, and the `CameraGroup` is shut down.

## Public Python API

```python
import _skellycam_rust

# Detection
cameras = _skellycam_rust.detect_cameras()  # → list[dict]

# Group management
manager = _skellycam_rust.PyO3CameraGroupManager()
group_id = manager.create_or_update_group(camera_configs_dict)

# Frame polling (called from asyncio)
payloads = manager.get_latest_frame_payloads(if_newer_than=-1)
# → dict[group_id: (frame_number, timestamp_ns, jpeg_bytes)]

# Teardown
manager.close_all_groups()
```

## Files

| File | Purpose |
|---|---|
| `mod.rs` | Python module init (`_skellycam_rust`), `detect_cameras()` pyfunction |
| `py_camera_group_manager.rs` | `PyO3CameraGroupManager` pyclass + pipeline thread |
| `types.rs` | Python-facing dataclass equivalents (`ImageResolution`, `CameraConfig`, etc.) |

## Design Decisions

**Thin adapter.** The PyO3 bridge does not contain business logic. It converts Python
types to Rust types, delegates to pure Rust modules, and converts results back.
This keeps the Rust code testable without a Python interpreter.

**Pipeline thread, not GIL.** JPEG encoding happens on a dedicated Rust thread
without the Python GIL. Python only locks briefly to swap the latest payload.
This prevents the camera pipeline from being blocked by Python garbage collection
or slow asyncio loop iterations.

**No CameraGroupManager wrapping.** `PyO3CameraGroupManager` does NOT wrap
`camera_group_manager::CameraGroupManager`. It manages its own group lifecycle
because it needs the pipeline thread + shared payload pattern. The pure Rust
manager is for non-Python contexts (CLI, tests, future WASM/other bindings).

**One group at a time.** `create_or_update_group()` closes any existing groups
before creating a new one. This keeps the Python API simple and matches the
current `skellycam` usage pattern. Multi-group support can be added later if needed.

## Build

```bash
cargo build --release
```
