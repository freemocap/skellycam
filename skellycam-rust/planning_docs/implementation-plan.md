# SkellyCam Rust — Implementation Plan

Status: **IN PROGRESS — Phase 1 complete, Phase 2 active**

Based on 9 analysis artifacts covering every component of the Python backend.

---

## Overview

Convert the SkellyCam Python backend (FastAPI + OpenCV + multiprocessing) into a single Rust binary (Axum + OpenCV + tokio). The frontend (Electron/React) remains unchanged. The HTTP API and WebSocket binary protocol are preserved bit-for-bit.

**Core principle**: Build each component as a standalone, testable unit before integration. Verify against the Python implementation at every boundary.

---

## Phase 0: Project Scaffolding ✅ COMPLETE

**Goal**: Cargo project, dependencies, module skeleton. No logic yet.

### Tasks

1. Create `skellycam-rust/skellycam/` as a Cargo binary+library project ✅
2. Declare dependencies in `Cargo.toml` ✅:
   - **Runtime**: `opencv` 0.98 with `videoio`, `imgproc`, `imgcodecs` features (camera via DirectShow), `image` 0.25 (rotation/resize/JPEG), `axum` 0.7 with `ws` (HTTP + WebSocket), `tokio` 1 with `full` features (async runtime), `serde`/`serde_json` (serialization), `utoipa` 5 + `utoipa-swagger-ui` 9 (OpenAPI), `tower` 0.5 + `tower-http` 0.6 with `cors` and `fs` (middleware), `anyhow` 1 + `thiserror` 2 (errors), `tracing` 0.1 + `tracing-subscriber` 0.3 with `env-filter` (logging), `uuid` 1 with `v4`, `chrono` 0.4 (time formatting), `csv` 1 (streaming writes), `ffmpeg-sidecar` 2 (ffmpeg auto-download)
   - **Commented out**: `polars` 0.41 with `lazy`, `csv-file` features (Phase 3 — recording analysis)
3. Set up `src/main.rs` (binary entry point) and `src/lib.rs` (library root) ✅
4. Declare module tree — all modules declared in `lib.rs` (currently placeholders for unimplemented modules) ✅
5. Configure `tracing_subscriber` for structured logging ✅
6. Configure `.cargo/config.toml` with OpenCV environment variables (link libs, link paths, include paths) ✅
7. Create `build.rs` to copy OpenCV runtime DLLs to target directory ✅
8. Verify: `cargo build` succeeds with all dependencies ✅

**Deliverable**: Compiling project with full dependency tree and module skeleton. **DONE.**

---

## Phase 1: Camera Core — Single Camera ✅ COMPLETE

**Goal**: Grab a frame from one camera on a dedicated thread, timestamp it, send it through the pipeline. No server, no multi-camera synchronization, no recording. Testable from `main.rs` with FPS reporting.

**Depends on**: Phase 0

### Tasks

#### 1.1: Camera Types (`camera/types.rs`) ✅

- `FrameData` enum — `Bgr(Vec<u8>)` variant (OpenCV's native pixel format is BGR)
- `FramePacket` struct — BGR pixel bytes, width, height, `grab_timestamp_nanoseconds` (i64, nanoseconds since process start), `identity: CameraIdentity`, `frame_number: i64`
- `CameraIdentity` struct — `display_name`, `camera_index`, `unique_identifier` (6-char hex hash of device path), `device_path`
- `MultiFramePayload` struct — `frames: Vec<FramePacket>`, `step: i64`, with `inter_camera_grab_spread_nanoseconds()` method
- `CameraCommand` enum — `Shutdown` (only command for now)
- `CameraEvent` enum — `Error(String)` (only event for now)
- `CameraHandle` struct — holds `command_sender: mpsc::Sender<CameraCommand>`, identity, width, height; with `send_shutdown()` convenience method

#### 1.2: Camera Thread (`camera/thread.rs`) ✅

- `spawn_camera_thread(index, requested_width, requested_height, identity)` — opens camera, spawns dedicated OS thread (`std::thread::spawn`, not tokio task)
- `open_camera(index, requested_width, requested_height)` — **two-phase MJPG setup**:
  - **Phase A (pre-warmup)**: Create `VideoCapture::new(index, CAP_DSHOW)`, set FOURCC to MJPG, set frame width/height, set buffer size to 1
  - **Warmup read**: `capture.read(&mut warmup)` — starts the DirectShow streaming filter graph
  - **Phase B (post-warmup)**: Set FOURCC to MJPG **again** (must re-set after graph is running; DirectShow renegotiates the media type on the first read and may drop MJPG). Do NOT change resolution after warmup (changing resolution resets FOURCC)
  - Read back actual config: resolution, FOURCC, FPS, backend name; print debug summary
- Returns `(CameraHandle, mpsc::Receiver<CameraEvent>, mpsc::Receiver<FramePacket>)`
- Grab loop (hot path per frame):
  1. Drain command channel (check for `Shutdown`)
  2. `capture.read(&mut frame)` — combined grab+retrieve (single call since OpenCV's `VideoCapture` is not `Send`: it must stay on the thread that created it)
  3. `performance_counter_nanoseconds()` — monotonic nanosecond timestamp since process start
  4. `frame.data_bytes()` — zero-copy access to BGR pixel bytes (OpenCV Mat internal pointer)
  5. Build `FramePacket` → `frame_sender.send(packet)` on `sync_channel(1)` (blocks if consumer not ready — structural backpressure already in place)
  6. Every 60 frames: print timing diagnostics (average grab interval, FPS, channel wait time)

#### 1.3: Timestamp Clock (`timestamps/performance.rs`) ✅

- `performance_counter_nanoseconds()` function — returns `i64` nanoseconds since process start
- Uses `OnceLock<Instant>` stored statically for the process start epoch
- Monotonic, high-precision, not subject to wall-clock adjustments

#### 1.4: Single-Camera Test Harness (`main.rs`) ✅

- Opens camera index 0 at 1280x720
- Spawns camera thread, receives `FramePacket` on main thread
- Reports FPS every 30 frames (rolling average)
- Runs for 500 frames then cleanly shuts down
- Reports summary: total frames, average FPS
- Verified: camera opens, grabs frames at 30fps, clean shutdown

**Deliverable**: Working single-camera capture with OpenCV + DirectShow + MJPG at 30fps. **DONE.**

---

## Phase 2: Multi-Camera Lockstep ← ACTIVE

**Goal**: Two or more cameras operating in synchronized lockstep via structural backpressure (`sync_channel(1)`). No server, no recording.

**Depends on**: Phase 1

**Architecture**:

The sync gate uses **structural backpressure** rather than polling atomics. Each camera thread runs on its own dedicated OS thread with a `VideoCapture` object that is not `Send` (must stay on the thread that created it). The gatherer thread calls `recv()` on all cameras' `sync_channel(1)` receivers — this is the lockstep barrier.

```
CAMERA THREAD 0                    CAMERA THREAD 1
  VideoCapture (not Send)            VideoCapture (not Send)
  grab() + retrieve()                 grab() + retrieve()
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

**Why grab+retrieve on same thread**: OpenCV's `VideoCapture` internally holds the DirectShow filter graph state. It is not `Send` — it must be created, used, and dropped on the same OS thread. The `retrieve()` call decodes the last grabbed frame from internal OpenCV state rather than from a buffer that could be handed to another thread. So the camera thread does both `grab()` (USB dequeue, ~1ms) and `retrieve()` (MJPG decode into BGR Mat, ~3-5ms), then sends the decoded `FramePacket` (BGR bytes from `data_bytes()`) downstream.

### Tasks

#### 2.1: Camera Enumeration (`camera/enumerate.rs`)

- `enumerate_directshow_cameras() -> anyhow::Result<Vec<CameraIdentity>>`
- Iterate indices 0..15: try `VideoCapture::new(i, CAP_DSHOW).is_opened()` → query device path (`CAP_PROP_GUID`), default resolution, backend name → build `CameraIdentity` → release capture
- Generate `unique_identifier` as 6-char hex hash of device path (matching Python pattern)
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

**Deliverable**: Working multi-camera synchronized capture with structural backpressure. Tested incrementally from 2 to 6 cameras.

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

**Mitigation**: OpenCV's `VideoCapture` with `CAP_DSHOW` initializes COM internally for the DirectShow backend. The camera runs on a dedicated OS thread (`std::thread::spawn`, not a tokio async task), which satisfies COM apartment requirements. The thread creates the capture, uses it, and drops it — all on the same thread. Already validated in Phase 1.

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
      types.rs                       # FramePacket, CameraCommand, CameraEvent, CameraIdentity, etc.
      thread.rs                      # spawn_camera_thread, open_camera (two-phase MJPG)
      enumerate.rs                   # enumerate_directshow_cameras

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
| 1 | **`opencv` crate for camera capture, `image` crate for JPEG encoding** | OpenCV with DirectShow is the only approach that reliably configured MJPG on Windows. The `image` crate (pure Rust) handles rotation, resize, and JPEG encoding for the frontend WebSocket payload. OpenCV is used only for camera capture and raw pixel extraction. |
| 2 | **Two-phase MJPG setup** | DirectShow requires the filter graph to be running before MJPG format negotiation completes. Set FOURCC → warmup `read()` → set FOURCC again → verify. Never change resolution after the graph starts (it resets FOURCC). This is the critical insight from weeks of experimentation. |
| 3 | **Grab + retrieve on same thread** | OpenCV's `VideoCapture` is not `Send` — it holds internal DirectShow filter graph state that must stay on one thread. `retrieve()` decodes from internal state, not from a buffer you can hand off. The dedicated OS thread does both `grab()` and `retrieve()`, then sends the decoded `FramePacket` via `sync_channel`. |
| 4 | **Structural backpressure via `sync_channel(1)`** | Replaces Python's polling-based sync gate. Capacity-1 channel means producer blocks if consumer hasn't received previous frame. Gatherer `recv()` from all cameras is the implicit barrier — zero polling, zero atomics. Slowest camera determines group framerate. |
| 5 | **ffmpeg via `ffmpeg-sidecar`** | Battle-tested, produces files that play everywhere, handles every edge case. `ffmpeg-sidecar` auto-downloads the correct binary on first launch — zero user setup. The subprocess pipe pattern is already proven in the webcam test project. |
| 6 | **Best-practice high-precision monotonic clock** | Uses `Instant::now()` with a `OnceLock<Instant>` process-start epoch to produce `i64` nanosecond timestamps via `performance_counter_nanoseconds()`. Monotonic, highest available precision, not subject to wall-clock adjustments. |
| 7 | **UUID with last 6 hex characters as group ID** | Matches Python behavior exactly. `uuid::Uuid::new_v4().to_string()[..6]` or equivalent truncation. |
| 9 | **Range requests via `tower_http::ServeDir`** | Natively supported. If incompatible with dynamic path routing, manual `Range` header parsing. |
| 8 | **`utoipa` for OpenAPI/Swagger** | Derive macros on request/response structs. Swagger UI served at `/docs`. |

---

## Milestones

| Milestone | Phases | Success Criterion |
|-----------|--------|-------------------|
| **M1: Camera Works** ✅ | 0-1 | Single camera grabs frames at 30fps, measures timestamps, clean shutdown |
| **M2: Sync Works** | 2 | Two cameras in lockstep, zero drift over 5 minutes, grab spread < 1ms |
| **M3: Recording Works** | 3 | Two-camera synchronized video files, timestamps, statistics |
| **M4: JPEG Validated** | 5 | Live camera frames display in a browser from Rust WebSocket |
| **M5: API Complete** | 4, 6 | All 17 endpoints return responses matching Python output |
| **M6: Frontend Works** | 7 | Full frontend workflow succeeds against Rust backend |
| **M7: Shippable** | 8 | Single binary, documented, CI builds for all platforms |
