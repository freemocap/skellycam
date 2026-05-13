# SkellyCam Rust — Implementation Plan

Status: **IN PROGRESS — Phase 1 updated (openpnp-capture PoC complete), Phase 2 active**

Based on 9 analysis artifacts covering every component of the Python backend.
Updated 2026-05-13: Replaced OpenCV with openpnp-capture based on PoC findings.

---

## Overview

Convert the SkellyCam Python backend (FastAPI + OpenCV + multiprocessing) into a single Rust binary (Axum + openpnp-capture + tokio). The frontend (Electron/React) remains unchanged. The HTTP API and WebSocket binary protocol are preserved bit-for-bit.

Camera capture uses the **openpnp-capture** C library (MIT licensed, cross-platform DirectShow/V4L2/AVFoundation) via manual Rust FFI bindings. This replaces OpenCV, eliminating the 500MB manual installation requirement. The library is compiled from source via cmake+nmake and linked statically.

**Core principle**: Build each component as a standalone, testable unit before integration. Verify against the Python implementation at every boundary.

---

## Phase 0: Project Scaffolding ✅ COMPLETE

**Goal**: Cargo project, dependencies, module skeleton. No logic yet.

### Tasks

1. Create `skellycam-rust/skellycam/` as a Cargo binary+library project ✅
2. Declare dependencies in `Cargo.toml` ✅:
   - **Runtime**: `openpnp-capture` (C library, statically linked via build.rs — cross-platform DirectShow/V4L2/AVFoundation), `image` 0.25 (rotation/resize/JPEG for frontend payloads), `axum` 0.7 with `ws` (HTTP + WebSocket), `tokio` 1 with `full` features (async runtime), `serde`/`serde_json` (serialization), `utoipa` 5 + `utoipa-swagger-ui` 9 (OpenAPI), `tower` 0.5 + `tower-http` 0.6 with `cors` and `fs` (middleware), `anyhow` 1 + `thiserror` 2 (errors), `tracing` 0.1 + `tracing-subscriber` 0.3 with `env-filter` (logging), `uuid` 1 with `v4`, `chrono` 0.4 (time formatting), `csv` 1 (streaming writes), `ffmpeg-sidecar` 2 (ffmpeg auto-download)
   - **Commented out**: `polars` 0.41 with `lazy`, `csv-file` features (Phase 3 — recording analysis)
   - **Build dependencies**: `cc` or manual `cmake` + `nmake` to compile openpnp-capture C library as a static `.lib`. On Windows, requires Visual Studio BuildTools (installed via chocolatey: `visualstudio2026buildtools` + `visualstudio2026-workload-vctools`).
3. Set up `src/main.rs` (binary entry point) and `src/lib.rs` (library root) ✅
4. Declare module tree — all modules declared in `lib.rs` (currently placeholders for unimplemented modules) ✅
5. Configure `tracing_subscriber` for structured logging ✅
6. Configure `.cargo/config.toml` for openpnp-capture static library link paths ✅
7. Create `build.rs` to link against openpnp-capture static library + transitive system libs (ole32, oleaut32, strmiids) ✅
8. Verify: `cargo build` succeeds with all dependencies ✅

**Deliverable**: Compiling project with full dependency tree and module skeleton. **DONE.**

---

## Phase 1: Camera Core — Single Camera ✅ COMPLETE (updated: openpnp-capture)

**Goal**: Grab a frame from one camera on a dedicated thread, timestamp it, send it through the pipeline. No server, no multi-camera synchronization, no recording. Testable from `main.rs` with FPS reporting.

**Camera backend**: openpnp-capture C library via manual Rust FFI (`extern "C"` blocks). Static link. No OpenCV dependency.

**Depends on**: Phase 0

### Tasks

#### 1.1: Camera Types (`camera/types.rs`) ✅

- `FrameData` enum — `Rgb(Vec<u8>)` variant (openpnp-capture decodes all formats to 24-bit RGB internally)
- `FramePacket` struct — RGB pixel bytes, width, height, `grab_timestamp_nanoseconds` (i64, nanoseconds since process start), `identity: CameraIdentity`, `frame_number: i64`
- `CameraIdentity` struct — `display_name`, `camera_index`, `unique_identifier` (camera's USB device path from openpnp-capture — persistent per USB port), `device_path`
- `MultiFramePayload` struct — `frames: Vec<FramePacket>`, `step: i64`, with `inter_camera_grab_spread_nanoseconds()` method
- `CameraCommand` enum — `Shutdown` (only command for now)
- `CameraEvent` enum — `Error(String)` (only event for now)
- `CameraHandle` struct — holds `command_sender: mpsc::Sender<CameraCommand>`, identity, width, height; with `send_shutdown()` convenience method

#### 1.2: Camera Thread (`camera/thread.rs`) ✅ (PoC proven, pending integration)

- `spawn_camera_thread(index, requested_width, requested_height, identity)` — opens camera, spawns dedicated OS thread (`std::thread::spawn`, not tokio task)
- `open_camera(ctx, index, requested_width, requested_height)` — **openpnp-capture format enumeration + two-phase MJPG setup**:
  - **Phase 1 — Enumerate formats**: Call `Cap_getNumFormats()` and `Cap_getFormatInfo()` to list all supported (width, height, fps, fourcc) combinations
  - **Phase 2 — Find MJPG match**: Iterate formats, find one matching `1280x720 MJPG 30fps` (fourcc = `0x47504A4D` on Windows DirectShow). Fall back to any MJPG format if 720p not available
  - **Phase 3 — Open stream**: `Cap_openStream(ctx, deviceID, formatID)` — this sets the format on the CAPTURE pin and builds the DirectShow filter graph. PoC discovery: use `PIN_CATEGORY_CAPTURE` (not PREVIEW) in the graph so that format re-application works correctly
  - **Phase 4 — Set exposure**: Turn off auto-exposure (`Cap_setAutoProperty(EXPOSURE, false)`) and set exposure to `-7` (1/128s ≈ 7.8ms) via `Cap_setProperty(EXPOSURE, -7)`. This forces a short sensor exposure time that allows the MJPEG encoder pipeline to run at full 30fps. Without this, auto-exposure in typical indoor lighting may choose longer exposures (1/20s–1/15s) that cap the sensor cycle rate at 15–20fps
  - **Phase 5 — Stabilize**: Capture ~30 frames to let the camera's image signal processor lock onto the new exposure setting
  - Read back actual config: resolution, FOURCC, FPS
- Returns `(CameraHandle, mpsc::Receiver<CameraEvent>, mpsc::Receiver<FramePacket>)`
- Grab loop (hot path per frame):
  1. Drain command channel (check for `Shutdown`)
  2. `Cap_hasNewFrame(ctx, stream)` — spin-wait (with `std::thread::yield_now()`) for next hardware frame. Non-blocking poll rather than blocking read allows command channel draining between frames
  3. `Cap_captureFrame(ctx, stream, buffer, bufferBytes)` — copies latest RGB frame into pre-allocated buffer
  4. `performance_counter_nanoseconds()` — monotonic nanosecond timestamp since process start
  5. Build `FramePacket` → `frame_sender.send(packet)` on `sync_channel(1)` (blocks if consumer not ready — structural backpressure already in place)
  6. Every 60 frames: print timing diagnostics (average grab interval, FPS, channel wait time)

#### 1.3: Timestamp Clock (`timestamps/performance.rs`) ✅

- `performance_counter_nanoseconds()` function — returns `i64` nanoseconds since process start
- Uses `OnceLock<Instant>` stored statically for the process start epoch
- Monotonic, high-precision, not subject to wall-clock adjustments

#### 1.4: Single-Camera Test Harness (`main.rs`) ✅ (PoC proven)

- Opens camera index 0 at 1280x720 via openpnp-capture FFI
- Spawns camera thread, receives `FramePacket` on main thread
- Reports FPS every 60 frames (rolling average)
- Runs for 300 frames then cleanly shuts down
- Reports summary: total frames, average FPS, average read latency
- Verified: all 6 USB cameras achieve 30fps at 1280x720 MJPG (some run slightly faster at ~33fps with short manual exposure)
- PoC located at `skellycam-rust/tools/openpnp-capture-poc/` — to be integrated into `skellycam` crate proper

**Deliverable**: Working single-camera capture with openpnp-capture + DirectShow + MJPG at 30fps. **PoC DONE, integration pending.**

---

## Phase 2: Multi-Camera Lockstep ← ACTIVE

**Goal**: Two or more cameras operating in synchronized lockstep via structural backpressure (`sync_channel(1)`). No server, no recording.

**Depends on**: Phase 1

**Architecture**:

The sync gate uses **structural backpressure** rather than polling atomics. Each camera thread runs on its own dedicated OS thread with a `CapContext` + `CapStream` that must stay on the creating thread (the internal DirectShow COM objects are thread-affine). The gatherer thread calls `recv()` on all cameras' `sync_channel(1)` receivers — this is the lockstep barrier.

```
CAMERA THREAD 0                    CAMERA THREAD 1
  CapContext + CapStream (not Send)    CapContext + CapStream (not Send)
  hasNewFrame() + captureFrame()       hasNewFrame() + captureFrame()
  frame_sender.send(packet) ───┐     frame_sender.send(packet) ───┐
    blocked if full             │       blocked if full            │
                                ▼                                  ▼
                        GATHERER THREAD
                  camera0_rx.recv() // blocks
                  camera1_rx.recv() // blocks
                  // barrier: all cameras at step N
                  MultiFramePayload { frames, step: N }
                  step += 1
                  // cameras unblock, proceed to frame N+1
```

**Why everything on the same thread**: openpnp-capture's `CapContext` and `CapStream` internally hold DirectShow COM objects that are thread-affine. They must be created, used, and destroyed on the same OS thread. openpnp-capture decodes camera frames to RGB888 internally (via sample grabber callback + BGR→RGB flip in `submitBuffer`), so `Cap_captureFrame` gives us RGB bytes directly. The camera thread polls `hasNewFrame`, captures, timestamps, and sends decoded `FramePacket` downstream.

### Tasks

#### 2.1: Camera Enumeration (`camera/enumerate.rs`)

- `enumerate_directshow_cameras() -> anyhow::Result<Vec<CameraIdentity>>`
- Use openpnp-capture API: `Cap_getDeviceCount()` → iterate with `Cap_getDeviceName()` and `Cap_getDeviceUniqueID()`. The unique ID is the USB device path (e.g. `\\?\usb#vid_0c45&pid_6366&mi_00#...`) — persistent per USB port, no hashing needed
- Filter out virtual cameras (OBS, LSVCam) by checking `Cap_getNumFormats() > 0`
- Generate `unique_identifier` as short hex hash of device path (matching Python pattern)
- Add `pub mod enumerate;` to `camera/mod.rs`, re-export the function

#### 2.2: CameraGroup Types (`camera_group/types.rs`)

```rust
pub struct CameraGroupConfig {
    pub camera_index: u32,
    pub requested_width: u32,
    pub requested_height: u32,
    pub identity: CameraIdentity,
}
```

#### 2.3: Gatherer (`camera_group/gatherer.rs`)

- `spawn_gatherer(frame_receivers: Vec<Receiver<FramePacket>>, event_receivers: Vec<Receiver<CameraEvent>>, camera_handles: Vec<CameraHandle>) -> (Receiver<MultiFramePayload>, JoinHandle<()>)`
- Gatherer loop on dedicated thread:
  1. Check all event channels (non-blocking `try_recv`) — log errors
  2. Lockstep barrier: `recv()` from every frame receiver — blocks until each camera sends frame N
  3. Assemble `MultiFramePayload { frames, step }`, step += 1
  4. Log inter-camera grab spread every 30 multiframes
  5. Send to downstream recorder/websocket channels (Phase 3+)
- If any camera channel disconnects → log, shut down all cameras, exit

#### 2.4: CameraGroup (`camera_group/group.rs`)

```rust
pub struct CameraGroup {
    pub group_identifier: String,
    pub camera_handles: Vec<CameraHandle>,
    pub gatherer_join_handle: Option<JoinHandle<()>>,
    pub multi_frame_receiver: Option<Receiver<MultiFramePayload>>,
}
```

- `CameraGroup::create(configs: Vec<CameraGroupConfig>) -> anyhow::Result<Self>`
  1. Validate unique camera indices
  2. For each config: `camera::spawn_camera_thread(index, width, height, identity)`
  3. Collect handles, frame receivers, event receivers
  4. `spawn_gatherer(frame_receivers, event_receivers, handles.clone())`
  5. Return `CameraGroup` with handles, gatherer join handle, multi-frame receiver
- `CameraGroup::shutdown(&self)` — calls `send_shutdown()` on all camera handles
- `CameraGroup::wait_for_shutdown(self)` — joins gatherer thread
- Shutdown ordering: send shutdown commands first (all cameras start exiting simultaneously), then join gatherer

#### 2.5: Multi-Camera Test Harness (`main.rs` update)

- CLI args: `--cameras N` (number to use), `--indices 0,1,2` (optional explicit indices)
- Flow: enumerate cameras → select N cameras → build `CameraGroupConfig` for each → `CameraGroup::create()` → consumer loop
- Consumer loop: `recv()` from multi-frame receiver, print aggregate stats every 30 multiframes (inter-camera grab spread, per-camera FPS, multiframe rate)
- Ctrl+C handler: call `camera_group.shutdown()`, wait for gatherer, report summary
- Default: run for 600 multiframes (~20 seconds at 30fps) or until Ctrl+C

#### 2.6: Incremental Validation Strategy

Test with increasing camera counts:

| Test | Cameras | Key Verified |
|------|---------|-------------|
| 2-camera | 2 | Lockstep mechanism works. Inter-camera spread < 3ms. Clean shutdown. |
| 3-camera | 3 | Backpressure scales. Slowest camera determines group FPS. |
| 4-camera | 4 | USB 2.0 bandwidth tested. Monitor for grab failures. |
| 5-camera | 5 | High USB load. May need USB 3.0 or separate host controllers. |
| 6-camera | 6 | Maximum load. May need reduced resolution (640x480). |

Each test: run for 300 multiframes minimum. Verify zero drift — all cameras at same frame number. The `sync_channel(1)` + gatherer `recv()` mathematically guarantees this; tests validate it under real USB/OS conditions.

**Deliverable**: Working multi-camera synchronized capture with structural backpressure via openpnp-capture. Tested incrementally from 2 to 6 cameras, all hitting 30fps.

---

## Phase 3: Recording Pipeline

**Goal**: Record synchronized multi-camera video to disk with per-frame timestamps. No server.

**Depends on**: Phase 2

### Tasks

#### 3.1: VideoRecorder (`recording/recorder.rs`)

Uses the proven ffmpeg subprocess pattern from `rust_webcam_app/src/recorder.rs`. ffmpeg is the reference implementation for video encoding — battle-tested, handles every codec and edge case, produces files that play everywhere.

**ffmpeg distribution**: `ffmpeg-sidecar` crate. On first launch, it downloads the correct prebuilt ffmpeg binary for the user's platform (~80MB, one-time). Subsequent launches use the cached binary with zero overhead. The user never installs anything manually — launch the app, it works.

**Subprocess pattern** (already working in the webcam test project):
- Spawn `ffmpeg` with `-f rawvideo -pixel_format rgb24` reading from `pipe:0`
- Encode to H.264 with `ultrafast` preset, `yuv420p` pixel format (`yuv420p` requires even dimensions — enforce `width & !1`, `height & !1` as fixed in the test project)
- `feed_frame(rgb_data, frame_number, timestamps)` — writes to ffmpeg stdin, collects metadata
- `finish() -> Vec<RecordedFrameMetadata>` — drops stdin (sends EOF), waits for ffmpeg, returns accumulated metadata
- `Drop` impl — kills ffmpeg on early exit (panic safety net)

#### 3.2: Recording Finalizer (`recording/finalizer.rs`)

- Receive `Vec<RecordedFrameMetadata>` from each camera
- Validate: all cameras have same frame count, sequential frame numbers
- Save `RecordingInfo` JSON with camera configs
- Compute durations from timestamps
- Write per-camera timestamp CSVs (streaming via `csv` crate)
- Build multi-frame DataFrame (via `polars`)
- Compute statistics per stage
- Write multi-frame CSV
- Save statistics JSON + text report

#### 3.3: Recording CSV Writer (`timestamps/csv_writer.rs`)

- Streaming CSV writer — writes one row per frame as recording progresses
- Resilient to crashes: data on disk alongside video
- Column naming: full words, no abbreviations, consistent with analysis doc #6

#### 3.4: Recording CSV Reader (`timestamps/csv_reader.rs`)

- Load per-camera CSVs into `polars` DataFrames
- Build multi-frame DataFrame via joins on frame number
- Compute cross-camera statistics

#### 3.5: Test — Record Two Cameras

- Start recording, capture 300 frames, stop recording
- Verify: two video files exist, same frame count
- Verify: per-camera timestamp CSVs exist, row count matches frame count
- Verify: multi-frame CSV exists with cross-camera sync statistics
- Verify: statistics JSON + text report generated
- Visual check: play both videos side by side — should be synchronized

**Deliverable**: Working multi-camera recording with timestamps and statistics.

---

## Phase 4: CameraGroupManager

**Goal**: CRUD lifecycle management for camera groups, exposed as a Rust API (not yet HTTP).

**Depends on**: Phase 3

### Tasks

#### 4.1: CameraGroupManager

- `HashMap<String, CameraGroup>` registry
- `create_or_update_camera_group(configs)` — creates new group or updates existing
- `start_recording_all_groups(recording_info)` — delegates to each group
- `stop_recording_all_groups() -> Vec<RecordingResult>` — delegates, collects
- `close_all_camera_groups()` — graceful shutdown
- `pause_unpause_all_groups()` — toggle
- `get_latest_frontend_payloads()` — for WebSocket relay
- `to_state_dict()` — serializable state for frontend

#### 4.2: Test — Manager Lifecycle

- Create two groups with different cameras
- Start/stop recording on each
- Verify state transitions
- Close all, verify clean shutdown

**Deliverable**: Working CameraGroupManager, testable from `main.rs`.

---

## Phase 5: Thin Vertical Slice — WebSocket Image to Browser

**Goal**: Get a JPEG-encoded frame from a real camera displayed in a browser via WebSocket. This is the riskiest integration point — it validates the JPEG encoder compatibility with the frontend before building the full HTTP API.

**Depends on**: Phase 2 (need multi-camera frames, but recording can wait)

### Tasks

#### 5.1: Payload Encoder (`frontend_payload/encoder.rs`)

- `PayloadHeaderFooter` struct — `#[repr(C)]`, 24 bytes
- `FrameHeader` struct — `#[repr(C)]`, 56 bytes
- `PayloadEncoder` with reusable `Vec<u8>` buffer
- `encode(frames, display_sizes) -> (multiframe_timestamp, &[u8])`

#### 5.2: Image Processing Pipeline (`frontend_payload/image_pipeline.rs`)

- Rotation: `image::imageops::rotate90` / `rotate180` / `rotate270`
- Resize: `image::imageops::resize` with `FilterType::Triangle`, default 50% or custom display size
- JPEG encode: `image::codecs::jpeg::JpegEncoder`, quality 80

#### 5.3: Minimal Axum WebSocket Server

- Single endpoint: `GET /skellycam/websocket/connect`
- On connect: spawn image relay task
- Image relay: receive from `watch::Receiver<Arc<MultiFramePayload>>`, encode, send binary
- No backpressure, no log relay, no state sender, no framerate — just images

#### 5.4: Test HTML Page

- Simple HTML file with a WebSocket client
- Receives binary messages, parses the protocol, extracts JPEGs
- Renders each camera's frame in a `<canvas>` or `<img>` element
- This is the **make-or-break test** for JPEG compatibility

#### 5.5: Test — Live Camera to Browser

- Start Rust backend with one camera
- Open test HTML page in browser
- Verify: frames appear, no visual corruption, update rate is smooth
- Test with different rotations, custom display sizes
- This is the **make-or-break test** for the full pipeline: camera → grab → decode → JPEG encode → WebSocket → browser

**Deliverable**: A browser window showing live camera frames streamed from Rust via WebSocket.

---

## Phase 6: Full HTTP API

**Goal**: Complete Axum server with all 17 endpoints, matching the Python API exactly.

**Depends on**: Phase 4 (CameraGroupManager), Phase 5 (WebSocket proven)

### Tasks

#### 6.1: Request/Response Models (`api/models.rs`)

Every Pydantic `BaseModel` → Rust struct with `serde` + `utoipa` derives:
- `CameraGroupCreateRequest`, `CreateCameraGroupResponse`
- `StartRecordingRequest`, `StopRecordingResponse`
- `DetectedCamerasResponse`, `DetectedMicrophonesResponse`
- `StatisticsSummary`
- All playback response models

#### 6.2: Camera Routes (`api/camera_routes.rs`)

- `POST /skellycam/camera/detect` — enumerate cameras
- `GET /skellycam/camera/microphone/detect` — enumerate microphones
- `POST /skellycam/camera/group/apply` — create/update group
- `POST /skellycam/camera/group/all/record/start` — start recording
- `GET /skellycam/camera/group/all/record/stop` — stop recording
- `DELETE /skellycam/camera/group/close/all` — close all
- `GET /skellycam/camera/group/all/pause_unpause` — toggle pause

#### 6.3: Playback Routes (`api/playback_routes.rs`)

- `GET /skellycam/playback/recordings` — list recordings
- `GET /skellycam/playback/{recording_id}/videos` — list videos
- `GET /skellycam/playback/{recording_id}/videos/{video_id}` — stream video (range requests)
- `GET /skellycam/playback/{recording_id}/timestamps` — all timestamps
- `GET /skellycam/playback/{recording_id}/videos/{video_id}/timestamps` — single video timestamps

#### 6.4: App Routes (`api/app_routes.rs`)

- `GET /health` — health check
- `GET /shutdown` — graceful shutdown
- `GET /` — redirect to `/docs`

#### 6.5: Router Assembly (`api/router.rs`)

- Merge all routes
- Add CORS layer (permissive, matching Python)
- Add `AppState` with `Arc<RwLock<CameraGroupManager>>`
- Add `utoipa` OpenAPI schema generation
- Serve Swagger UI at `/docs`

#### 6.6: Error Handling (`api/error.rs`)

- `AppError` enum with `IntoResponse` impl
- 500 → `{ "detail": "<message>" }` (matching Python format)
- Logging via `tracing`

#### 6.7: Full WebSocket Server (`websocket/server.rs`)

Complete the 4-task WebSocket server from Phase 5:
- Image relay (binary, backpressure-aware)
- Log relay (from `tracing` layer)
- State sender (every 1s, only when changed)
- Client message handler (frameNumber acks, displayImageSizes, ping/pong)
- Framerate tracking (server + display)

#### 6.8: Serve Test HTML Page

- Add a route to serve the test HTML page from the API (e.g., `GET /test`)
- The page is a single self-contained HTML file with inline CSS and JavaScript
- Includes:
  - **WebSocket display**: live camera frames rendered in `<canvas>` or `<img>` elements
  - **HTTP endpoint buttons**: one button per camera/recording endpoint, with form inputs for required fields and sensible defaults (camera index, recording name, etc.)
  - **Status display**: shows responses from HTTP calls, connection status, framerate
  - **Framerate indicator**: server and display FPS
- Design goal: test the full pipeline without needing the Electron frontend

#### 6.9: Test — Full API via Test HTML Page

- Start Rust backend
- Open test HTML page in browser
- Test full workflow using only the test page:
  - Detect cameras, create group, start/stop recording, pause/unpause, close group
  - Verify WebSocket frames stream correctly throughout
  - Verify recording files exist and are playable

**Deliverable**: Complete HTTP API server. Full pipeline testable via single-page test HTML client.

---

## Phase 7: Frontend Integration Testing

**Goal**: Verify the Rust backend works with the real Electron/React frontend as a secondary validation. Primary testing is done via the test HTML page built in Phase 6.

**Depends on**: Phase 6

### Tasks

1. Start Rust backend on `localhost:53117`
2. Point existing frontend at it
3. Walk through full workflow and note any discrepancies
4. Fix any issues found

**Deliverable**: Confirmation that the real frontend works against the Rust backend.

---

## Phase 8: Deployment & Distribution

**Goal**: Single binary distribution with zero user setup. "It just works."

**Depends on**: Phase 7

### Tasks

1. `cargo build --release` — optimized binary
2. Bundle ffmpeg binary alongside the executable (if pure Rust encoding wasn't viable):
   - `ffmpeg-sidecar` crate for automatic download + caching, OR
   - Manual inclusion in release archive
   - Check bundled location first, fall back to system PATH
3. CI/CD: GitHub Actions for Windows/macOS/Linux builds
4. Versioning: match Python SkellyCam version initially, diverge as needed
5. Documentation: README, build instructions, API docs at `/docs` (Swagger)

---

## Testing Strategy

### Primary: Test HTML Page

The built-in test HTML page (served at `GET /test`) is the primary testing tool during development. It provides:
- Live WebSocket frame display for visual verification
- Buttons for every HTTP endpoint with form inputs and default values
- Status display for API responses and connection state
- Framerate indicator

Every phase from Phase 5 onward is tested first through this page.

### Secondary: Real Frontend

Phase 7 validates against the actual Electron/React frontend as a final check.

### Automated Tests

| Phase | What to Test | How to Test |
|-------|-------------|------------|
| 1 | Single camera capture | Manual: minifb preview, timing output |
| 2 | Multi-camera lockstep | Automated: assert frame numbers match across cameras every cycle; inter-camera grab spread < 1ms |
| 3 | Recording pipeline | Automated: verify file existence, frame counts, CSV row counts, stats output |
| 4 | CameraGroupManager | Automated: create/update/close lifecycle, state transitions |
| 5 | Camera-to-browser pipeline | Manual: test HTML page for visual check; automated: struct layout test (assert header/footer sizes) |
| 6 | HTTP API + WebSocket | Manual: test HTML page for full workflow; automated: request/response shape tests |
| 7 | Frontend integration | Manual: full workflow with real frontend |
| 8 | Deployment | Automated: CI builds for all platforms |

### Future: Mock Camera System

For automated testing without physical cameras, build a mock camera that replays pre-recorded video files as if they were live camera frames. This mirrors the Python pytest mock pattern. A recorded SkellyCam session (synchronized multi-camera video + timestamp CSVs) becomes the test fixture — the mock reads frames from video files and feeds them through the pipeline at the recorded framerate. This enables CI testing of the full pipeline without hardware.

---

## Risk Mitigation

### Risk 1: ffmpeg-sidecar Download Failure (LOW)

**Mitigation**: `ffmpeg-sidecar` handles download retries and cache validation. If the download fails (no internet, firewall), display a clear error message with a link to manual ffmpeg installation as a fallback. The download is a one-time event — most users never think about it.

### Risk 2: Windows COM/STA Threading (LOW)

**Mitigation**: openpnp-capture's DirectShow backend initializes COM internally. The camera runs on a dedicated OS thread (`std::thread::spawn`, not a tokio async task), which satisfies COM apartment requirements. The thread creates the context, opens the stream, captures frames, and tears down — all on the same thread. Already validated in Phase 1 PoC.

---

## Proposed File Structure

```
skellycam-rust/skellycam/
  Cargo.toml
  src/
    main.rs                          # Binary entry: CLI args, server startup
    lib.rs                           # Library root: module declarations

    camera/
      mod.rs                         # Re-exports
      types.rs                       # FramePacket(Rgb), CameraCommand, CameraEvent, CameraIdentity, etc.
      ffi.rs                         # extern "C" declarations for openpnp-capture API
      thread.rs                      # spawn_camera_thread, open_camera (format enum + MJPG + exposure fix)
      enumerate.rs                   # enumerate cameras via openpnp-capture Cap_getDeviceName/UniqueID

    camera_group/
      mod.rs                         # Re-exports
      types.rs                       # CameraGroupConfig, CameraGroupConfigSource
      group.rs                       # CameraGroup: create, shutdown, wait_for_shutdown
      gatherer.rs                    # Gatherer: lockstep recv barrier, MultiFramePayload assembly

    camera_group_manager/
      mod.rs                         # CameraGroupManager: CRUD, recording, state

    recording/
      mod.rs                         # Re-exports
      recorder.rs                    # VideoRecorder: ffmpeg subprocess per camera
      finalizer.rs                   # RecordingFinalizer: validation, timestamp processing
      information.rs                 # RecordingInformation: paths, UUIDs, folder schema

    timestamps/
      mod.rs                         # Re-exports
      stages.rs                      # TimestampStage enum, display names
      frame_timestamps.rs            # FrameTimestamps struct, to_stage_map conversion
      durations.rs                   # FrameDurations, compute()
      statistics.rs                  # RecordingTimestampStatistics, MetricStatistics
      timebase.rs                    # TimebaseMapping
      csv_writer.rs                  # Streaming CSV output (csv crate)
      csv_reader.rs                  # Polars-based CSV loading and analysis

    websocket/
      mod.rs                         # Re-exports
      server.rs                      # WebSocket handler: 4 concurrent tasks
      binary_protocol.rs             # PayloadHeaderFooter, FrameHeader structs
      messages.rs                    # FramerateUpdateMessage, AppStateMessage, etc.

    api/
      mod.rs                         # Re-exports
      router.rs                      # Axum router assembly
      application_state.rs           # AppState struct
      error.rs                       # AppError, IntoResponse
      models.rs                      # All request/response serde + utoipa structs
      camera_routes.rs               # Camera endpoints
      playback_routes.rs             # Playback endpoints
      application_routes.rs          # Health, shutdown, root redirect

    frontend_payload/
      mod.rs                         # Re-exports
      encoder.rs                     # PayloadEncoder with reusable buffer
      image_pipeline.rs              # Rotate, resize, JPEG encode
```

---

## Confirmed Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **openpnp-capture (C library via manual FFI) for camera capture, `image` crate for JPEG encoding** | openpnp-capture is a cross-platform (Windows/Linux/macOS) MIT-licensed C library wrapping DirectShow/V4L2/AVFoundation. Compiles to a 4.5MB static library — no 500MB OpenCV installation needed. Built via cmake+nmake (Windows) and linked statically via `build.rs`. The `image` crate (pure Rust) handles rotation, resize, and JPEG encoding for the frontend WebSocket payload. |
| 2 | **CAPTURE pin (not PREVIEW) + manual exposure for 30fps MJPG** | openpnp-capture originally used `PIN_CATEGORY_PREVIEW` for streaming, which worked for LifeCam 3000 but caused 15–20fps on our multi-camera USB rigs. Switching to `PIN_CATEGORY_CAPTURE` matches OpenCV's DirectShow backend architecture. Additionally, setting manual exposure to `-7` (1/128s) forces a short sensor exposure time — auto-exposure in indoor lighting typically picks longer exposures (1/15s–1/20s) that cap the sensor cycle rate. The combination of CAPTURE pin + manual short exposure achieves consistent 30fps on all tested cameras. |
| 3 | **openpnp-capture objects stay on dedicated OS thread** | The `CapContext` is created, used, and destroyed on the same OS thread that runs the grab loop. openpnp-capture's internal DirectShow COM objects must stay on their creating thread. The dedicated OS thread does the grab loop (poll `hasNewFrame`, capture frame, timestamp) and sends decoded RGB `FramePacket` via `sync_channel`. |
| 4 | **Structural backpressure via `sync_channel(1)`** | Replaces Python's polling-based sync gate. Capacity-1 channel means producer blocks if consumer hasn't received previous frame. Gatherer `recv()` from all cameras is the implicit barrier — zero polling, zero atomics. Slowest camera determines group framerate. |
| 5 | **ffmpeg via `ffmpeg-sidecar`** | Battle-tested, produces files that play everywhere, handles every edge case. `ffmpeg-sidecar` auto-downloads the correct binary on first launch — zero user setup. The subprocess pipe pattern is already proven in the webcam test project. |
| 6 | **Best-practice high-precision monotonic clock** | Uses `Instant::now()` with a `OnceLock<Instant>` process-start epoch to produce `i64` nanosecond timestamps via `performance_counter_nanoseconds()`. Monotonic, highest available precision, not subject to wall-clock adjustments. |
| 7 | **UUID with last 6 hex characters as group ID** | Matches Python behavior exactly. `uuid::Uuid::new_v4().to_string()[..6]` or equivalent truncation. |
| 8 | **`utoipa` for OpenAPI/Swagger** | Derive macros on request/response structs. Swagger UI served at `/docs`. |
| 9 | **Range requests via `tower_http::ServeDir`** | Natively supported. If incompatible with dynamic path routing, manual `Range` header parsing. |

---

## Milestones

| Milestone | Phases | Success Criterion |
|-----------|--------|-------------------|
| **M1: Camera Works** ✅ | 0-1 | Single camera grabs frames at 30fps via openpnp-capture, measures timestamps, clean shutdown. Validated on 6 USB cameras at 1280x720 MJPG. |
| **M2: Sync Works** | 2 | Two cameras in lockstep, zero drift over 5 minutes, grab spread < 1ms |
| **M3: Recording Works** | 3 | Two-camera synchronized video files, timestamps, statistics |
| **M4: JPEG Validated** | 5 | Live camera frames display in a browser from Rust WebSocket |
| **M5: API Complete** | 4, 6 | All 17 endpoints return responses matching Python output |
| **M6: Frontend Works** | 7 | Full frontend workflow succeeds against Rust backend |
| **M7: Shippable** | 8 | Single binary, documented, CI builds for all platforms |
