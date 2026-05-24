# SkellyCam Rust

A ground-up Rust re-architecture of the SkellyCam camera backend — replacing the original Python multiprocessing + OpenCV pipeline with a pure Rust, thread-per-camera architecture built on `openpnp-capture`, `tokio`, and `axum`.

**The goal:** correct multi-camera synchronization at real framerates (30+ fps per camera), with a Python bridge that drops into the existing SkellyCam application without changing the frontend.

## Quick Start

```bash
# Build (always use --release — debug builds are too slow for the camera hot loop)
cargo build --release

# Run the HTTP + WebSocket server
cargo run --release -- --serve

# Open the test UI in a browser
# http://localhost:53117/test

# Run the full test suite (requires at least 2 cameras available)
# see #Running Tests section or the top of 
cargo run --release -- test all --max-cameras 2

# Run standard Rust unit tests (no hardware required)
cargo test --release
```

The server starts on `http://localhost:53117`. The existing SkellyCam Python frontend connects to it with no configuration changes — it speaks the same HTTP API and WebSocket binary protocol.

## How It Works

```
Camera 0 (OS thread) ──┐
Camera 1 (OS thread) ──┼── Gatherer Thread ──→ Dispatcher Thread ──→ WebSocket (frontend)
Camera N (OS thread) ──┘    barrier(N+1)         encodes JPEG           HTTP API (REST)
                                                   manages recording      PyO3 Bridge (Python)
```

Each camera owns a dedicated OS thread with a thread-affine DirectShow COM context (via `openpnp-capture`). Cameras capture independently, then rendezvous at a `BreakableBarrier` — USB transfer and JPEG copy happen in parallel. The dispatcher thread encodes frontend payloads and manages recording (ffmpeg + CSV timestamps) without holding the Python GIL.

## Project Layout

```
skellycam-rust/
├── src/
│   ├── main.rs              # Binary entry point: CLI dispatch + server
│   ├── lib.rs               # Library root: module declarations + init_logging()
│   ├── cli.rs               # CLI argument parsing (clap)
│   ├── logging.rs           # Custom tracing formatter
│   ├── api/                 # HTTP API layer (Axum)
│   ├── camera/              # Low-level camera device abstraction
│   ├── camera_group/        # Synchronized multi-camera pipeline
│   ├── camera_group_manager/# Registry for multiple camera groups
│   ├── websocket/           # WebSocket server for frame streaming
│   ├── frontend_payload/    # JPEG encoding + image pipeline
│   ├── recording/           # Video recording subsystem (ffmpeg)
│   ├── timestamps/          # Performance clock + CSV timestamp writing
│   ├── decode/              # JPEG-to-RGB decode utilities
│   ├── pyo3_bridge/         # Python bindings (PyO3)
│   └── tests/               # CLI-driven integration test harness
├── tests/                   # Standard #[test] integration tests
├── tools/                   # Build scripts + Python test helpers
├── rearchitecture-docs/     # Architecture documentation
├── Cargo.toml
├── build.rs                 # Downloads openpnp-capture + turbojpeg static libs
├── pyproject.toml           # Maturin build config for Python wheel
└── FRAMERATE_METRIC_DEFINITIONS.md
```

### Per-Module READMEs

Most source modules contain their own README with architecture details, design decisions, and thread model documentation:

| README | Module |
|--------|--------|
| `src/camera/camera_README.md` | Camera abstraction, thread model, state machine |
| `src/camera_group/camera_group_README.md` | CameraGroup lifecycle, gatherer thread, API |
| `src/camera_group_manager/camera_group_manager_README.md` | Manager registry for multiple groups |
| `src/pyo3_bridge/pyo3_bridge_README.md` | Python bindings adapter, GIL safety, thread model |

Start with the camera README if you want to understand how frames flow from hardware into the system.

## Running Tests

### CLI Test Harness (requires cameras)

```bash
cargo run --release -- test detect                  # Camera detection
cargo run --release -- test lifecycle --cameras 2   # Start → stream → shutdown
cargo run --release -- test multi --cameras 3 --max-loops 60  # Multi-camera sync
cargo run --release -- test recording --cameras 2 --output PATH  # Full recording cycle
cargo run --release -- test pause --cameras 2       # Pause/unpause/toggle
cargo run --release -- test api                     # HTTP + WebSocket (requires running server)
cargo run --release -- test rotate                  # Lossless JPEG rotation
cargo run --release -- test manager                 # CameraGroupManager lifecycle
cargo run --release -- test update exposure         # Mid-stream config updates
cargo run --release -- test all                     # Full suite
```

### Standard Unit Tests (no hardware)

```bash
cargo test --release                                           # All unit tests
cargo test --release camera::frame_loop::tests::              # Frame state machine
cargo test --release camera_group::                            # Camera group unit tests
```

### Python Integration Tests

```bash
python tools/test_rust_backend.py           # Smoke test: Rust backend via PyO3
python tools/test_pyo3_bridge_hardware.py   # End-to-end hardware test
python tools/test_api_integration.py        # HTTP API test against running server
```

## Python Bridge (PyO3)

The Rust camera engine is available to Python as `_skellycam_rust` via PyO3 and maturin.

### Building the Python Module

```bash
# Install maturin if you haven't already
pip install maturin

# Build and install into the active Python environment
cd skellycam-rust
maturin develop --release
```

### Enabling / Disabling in SkellyCam

The Python-to-Rust bridge is controlled by a flag in the SkellyCam Python codebase:

```python
# skellycam/core/camera_group/camera_group_manager.py, line 31
USE_RUST_BACKEND: bool = True
```

Set this to `False` to fall back to the original Python multiprocessing + OpenCV backend. When `True`, `get_camera_group_manager()` returns a `RustCameraGroupManager` instead of the Python `CameraGroupManager` — it's a drop-in replacement that speaks the same interface.

### What the Bridge Provides

```python
import _skellycam_rust

cameras = _skellycam_rust.detect_cameras()           # Hardware detection
manager = _skellycam_rust.CameraGroupManager()       # Group lifecycle
group_id = manager.create_or_update_group(configs)    # Start streaming
payloads = manager.get_latest_frame_payloads()        # Poll frames (call from asyncio)
manager.start_recording(output_dir="...", label="...")# Start recording
summary = manager.stop_recording()                   # Stop recording
manager.apply_configs(group_id, updated_configs)      # Mid-stream config changes
manager.close_all_groups()                            # Teardown
```

The dispatcher thread encodes JPEG payloads without holding the Python GIL — Python only locks briefly to swap the latest frame on each asyncio iteration.

## Building from Source: openpnp-capture

The `build.rs` script automatically downloads pre-built `openpnp-capture` and `turbojpeg` static libraries from the [jonmatthis/openpnp-capture](https://github.com/jonmatthis/openpnp-capture) fork's GitHub Releases. Every build queries the GitHub API for the latest release tag. If a newer tag is found, the new artifact is downloaded. If the same tag is already cached in `target/build-artifacts/`, the download is skipped.

If the GitHub API is rate-limited, set the skip flag to use cached artifacts:

```bash
SKIP_OPENPNP_DOWNLOAD=1 cargo build --release
```

### The openpnp-capture Fork

The upstream `openpnp-capture` library does not ship pre-built binaries. The [jonmatthis/openpnp-capture](https://github.com/jonmatthis/openpnp-capture) fork provides pre-built static libraries for all platforms — Windows (x86_64, ARM64), Mac (x86_64, ARM64), and Linux (x86_64, ARM64) — via GitHub Releases.

**Note:** The pre-built binaries exist for all platforms, and `build.rs` maps all six target triples (Windows x86_64/ARM64, macOS Intel/Apple Silicon, Linux x86_64/ARM64). Only the Windows targets have been tested end-to-end — Mac and Linux may encounter issues with system library linking or camera enumeration at runtime.

## Current Status

### Windows — Solid Proof of Concept

The Windows build is the primary development target and works well for the core pipeline:

- Camera detection across multiple devices
- Multi-camera synchronized streaming at real framerates (30 fps per camera)
- Recording to video (ffmpeg) with per-frame CSV timestamps
- Mid-stream config updates (exposure, resolution, framerate, add/remove cameras)
- Full HTTP API + WebSocket binary protocol parity with the Python backend
- Swagger UI at `/docs` and interactive test page at `/test`

**Known issues:** There may be edge cases around camera lifecycle management — hot-plugging cameras mid-session or rapid start/stop/start cycles can expose race conditions that haven't been fully addressed.

### Mac and Linux — Untested

**Mac and Linux are not currently tested.** The code is structured to be cross-platform (the `openpnp-capture` FFI bindings are platform-agnostic, and the Rust code has no Windows-specific dependencies), but these platforms have not been exercised. Potential issues:

- **build.rs target mapping:** Mac (`x86_64-apple-darwin`, `aarch64-apple-darwin`) and Linux (`x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`) target triples are now mapped in `target_triple_to_artifact()`. The pre-built artifacts can be downloaded and linked, but this hasn't been tested on real hardware.
- **Camera enumeration:** DirectShow is Windows-only. On Mac, `openpnp-capture` uses AVFoundation; on Linux, V4L2. Enumeration behavior may differ.
- **JPEG encoding:** The `turbojpeg` static library is provided for all platforms by the fork, but hasn't been tested on Mac or Linux.

If you are testing on Mac or Linux, the first step is adding your target triple to `target_triple_to_artifact()` in `build.rs`. Contributions (especially CI runners and platform-specific fixes) are very welcome.

## Architecture Documentation

The `rearchitecture-docs/` directory contains two sets of documentation:

### Re-architecture Playbook (`rearchitecture-docs/rearchitecture-playbook/`)

The 5-step methodology used to re-architect the Python backend into Rust. Useful if you are porting other FreeMoCap components:

1. Understand the problem
2. Extract invariants (WHAT, not HOW)
3. Separate Python-specific concerns
4. Design the Rust architecture from invariants
5. Reusable patterns catalog

### SkellyCam Architecture (`rearchitecture-docs/skellycam-architecture/`)

Nine documents covering every architectural component, each comparing the Python implementation with the Rust implementation:

| # | Document | Component |
|---|----------|-----------|
| 01 | System Startup | Process model, lifecycle, shutdown |
| 02 | Camera Group Manager | Group lifecycle, config updates |
| 03 | Camera Sync Gate | Multi-camera lockstep, capture loop |
| 04 | Frame Fan-Out | Gatherer to frontend + recorder |
| 05 | Recording Pipeline | Video encoding, metadata, finalization |
| 06 | Timestamp Pipeline | Per-frame timing, performance clock |
| 07 | HTTP API Surface | Endpoints, JSON shapes, error handling |
| 08 | WebSocket Binary Protocol | Wire format, image processing |
| 09 | Channel Architecture | Thread communication, sync primitives |

These are the best resource for understanding the mapping between the Python and Rust implementations and the reasoning behind each design decision.

## API Endpoints

When the server is running (`cargo run --release -- --serve`):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/skellycam/camera/detect` | Enumerate connected cameras |
| `POST` | `/skellycam/camera/group/apply` | Create or update a camera group |
| `POST` | `/skellycam/camera/group/start` | Start streaming |
| `POST` | `/skellycam/camera/group/stop` | Stop streaming |
| `POST` | `/skellycam/recording/start` | Begin recording |
| `POST` | `/skellycam/recording/stop` | End recording |
| `POST` | `/skellycam/recording/pause` | Pause recording |
| `POST` | `/skellycam/recording/unpause` | Resume recording |
| `POST` | `/skellycam/shutdown` | Graceful server shutdown |
| `GET`  | `/skellycam/websocket` | WebSocket upgrade for binary frames |
| `GET`  | `/docs` | Swagger UI (OpenAPI) |
| `GET`  | `/test` | Interactive test page |

The Rust server matches the Python server's API surface — the existing SkellyCam frontend connects to either backend without modification (except I dont think the `playback/` stuff works yet)

## Implementation Notes

**Always use `--release` for perforamnce testing (i.e. `cargo run --release` not `cargo run`).** The camera capture hot loop processes JPEG frames from multiple cameras at 30 fps. Debug builds are an order of magnitude too slow for this workload.

**Thread-per-camera model.** Each camera gets a dedicated OS thread because `openpnp-capture`'s DirectShow COM context is thread-affine — the capture device must be opened, configured, and polled on the same thread for its entire lifetime. The thread IS the camera.

**No GIL during encoding.** JPEG encoding runs on the dispatcher thread without the Python GIL. Python only acquires a brief lock to swap the latest frontend payload. This prevents the camera pipeline from being blocked by Python garbage collection or a slow asyncio loop iteration.

**Runtime enums, not type-state.** Both `Camera` and `CameraGroup` use runtime state enums rather than Rust's compile-time type-state pattern, because they own OS threads and channel endpoints that must persist across state transitions.

## Troubleshooting

**Build fails downloading openpnp-capture:**
```bash
SKIP_OPENPNP_DOWNLOAD=1 cargo build --release
```
This uses cached artifacts in `target/build-artifacts/`. If no cache exists, you will need GitHub API access or a local build of `openpnp-capture`.

**Camera detection returns zero devices:**
- On Windows: ensure cameras are connected and not in use by another application (DirectShow is exclusive).
- On Mac/Linux: check that `openpnp-capture` was built with the correct media backend (AVFoundation / V4L2).

**Port 53117 already in use:**
Another instance of the SkellyCam server (Python or Rust) is running. Stop it first.

**Debug build runs slower than expected (e.g. 10-20fps looping from 20 fps cameras) :**
Use `--release`. The camera hot loop cannot keep up at debug optimization levels.
