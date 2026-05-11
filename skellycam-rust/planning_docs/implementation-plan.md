# SkellyCam Rust — Implementation Plan

Status: **PROPOSED — awaiting review and approval**

Based on 9 analysis artifacts covering every component of the Python backend.

---

## Overview

Convert the SkellyCam Python backend (FastAPI + OpenCV + multiprocessing) into a single Rust binary (Axum + nokhwa + tokio). The frontend (Electron/React) remains unchanged. The HTTP API and WebSocket binary protocol are preserved bit-for-bit.

**Core principle**: Build each component as a standalone, testable unit before integration. Verify against the Python implementation at every boundary.

---

## Phase 0: Project Scaffolding

**Goal**: Cargo project, dependencies, module skeleton. No logic yet.

### Tasks

1. Create `skellycam-rust/skellycam/` as a Cargo binary+library project
2. Declare dependencies in `Cargo.toml`:
   - **Runtime**: `nokhwa` (camera), `image` (rotation/resize/JPEG), `axum` (HTTP), `tokio` (async runtime), `serde`/`serde_json` (serialization), `utoipa` (OpenAPI), `tower-http` (CORS), `anyhow` (errors), `tracing` (logging), `bytemuck` (safe transmutation), `csv` (streaming writes), `polars` (dataframe analysis), `chrono` (time formatting)
   - **Dev**: `tokio-test`, test utilities
3. Set up `src/main.rs` (binary entry point) and `src/lib.rs` (library root)
4. Declare module tree (all modules, initially empty or with placeholder `pub fn`)
5. Configure `tracing_subscriber` for structured logging
6. Verify: `cargo build` succeeds with all dependencies

**Deliverable**: Compiling project with full dependency tree and empty module skeleton.

---

## Phase 1: Camera Core — Single Camera

**Goal**: Grab a frame from one camera on a dedicated thread, timestamp it, send it through the pipeline. No server, no multi-camera sync, no recording. Testable from `main.rs` with a simple preview loop.

**Depends on**: Phase 0

### Tasks

#### 1.1: Camera Types (`camera/types.rs`)

- `CameraCommand` enum — `AdjustControl`, `GetControlInfo`, `Shutdown`
- `CameraEvent` enum — `Frame(RawFrame)`, `ControlAdjusted`, `Error`
- `RawFrame` struct — raw bytes from camera, timestamp, camera identifier, camera index
- `FramePacket` struct — decoded RGB image, timestamps, camera identifier
- Port `CameraMetadata` (resolution, controls) from existing webcam test project

#### 1.2: Camera Thread (`camera/thread.rs`)

- `spawn_camera_thread()` — opens camera, enters grab loop
- Grab loop: `camera.frame()` → timestamp → `sync_channel.send(RawFrame)`
- Processes `CameraCommand`s via `sync_channel` receiver
- Thin and fast — camera thread does ONLY grab, not decode

#### 1.3: Decoder Thread (`camera/decoder.rs`)

- Receives `RawFrame` from camera thread
- Decodes raw buffer → RGB (MJPEG/YUY2 → RgbImage)
- Timestamps decode operation
- Sends `FramePacket` downstream via `sync_channel`

#### 1.4: Timestamp Hot-Path Struct (`timestamps/frame_timestamps.rs`)

- `FrameTimestamps` struct — 6 `i64` fields (pre/post grab, pre/post decode, pre/post record)
- Stack-allocated, `Copy`, zero heap
- `TimestampStage` enum — extensible stage definitions
- `to_stage_map()` conversion for storage/CSV output

#### 1.5: Single-Camera Main Loop Test

- `main.rs` test: spawn camera thread + decoder thread
- Receive `FramePacket` on main thread
- Display in minifb window (from existing webcam test project)
- Print per-stage timing averages every 60 frames
- Verify: camera opens, grabs frames, decodes, displays

**Deliverable**: Working single-camera capture with grab/decode split and timestamp measurement.

---

## Phase 2: Multi-Camera Lockstep

**Goal**: Two or more cameras operating in synchronized lockstep via structural backpressure. No server, no recording.

**Depends on**: Phase 1

### Tasks

#### 2.1: CameraGroup Channels (`camera_group/channels.rs`)

Define all channel types for a camera group:

```rust
pub struct CameraGroupChannels {
    /// Camera thread → decoder thread (one per camera)
    pub raw_frame_senders: HashMap<String, SyncSender<RawFrame>>,
    pub raw_frame_receivers: HashMap<String, Receiver<RawFrame>>,

    /// Decoder thread → gatherer (one per camera)
    pub decoded_frame_senders: HashMap<String, SyncSender<FramePacket>>,
    pub decoded_frame_receivers: HashMap<String, Receiver<FramePacket>>,

    /// Gatherer fan-out: every frame
    pub recorder_sender: UnboundedSender<Arc<MultiFramePayload>>,

    /// Gatherer fan-out: latest only
    pub websocket_sender: watch::Sender<Arc<MultiFramePayload>>,

    /// Camera control (one per camera)
    pub control_senders: HashMap<String, Sender<ControlCommand>>,
}
```

#### 2.2: CameraOrchestrator (`camera_group/orchestrator.rs`)

- Pause/unpause: sets `AtomicBool` per camera, awaits state change
- Recording boundaries: `first_recording_frame_number: AtomicI64`, `last_recording_frame_number: AtomicI64`
- `should_record_frame(frame_number) -> (bool, bool)` — same logic as Python
- Gatherer loop: `recv()` from all decoder channels → assemble `MultiFramePayload` → fan out to recorder + WebSocket

#### 2.3: CameraGroup (`camera_group/group.rs`)

- `CameraGroup::create(configs)` — spawns camera threads + decoder threads per camera
- `start()` — begins gatherer loop
- `pause()` / `unpause()` — delegates to orchestrator
- `close()` — graceful shutdown of all threads
- Two-phase startup: spawn → receive extracted configs → proceed (same pattern as Python, but with channels instead of PubSub)

#### 2.4: Test — Two-Camera Lockstep

- `cargo run -- --cameras 0,1` — opens two cameras
- Verify: both cameras produce frames at the same step number
- Print inter-camera grab timing spread per multiframe
- Test pause/unpause — verify both cameras pause within one frame
- Run for 60 seconds, verify no drift (all cameras at same frame number at all times)

**Deliverable**: Working multi-camera synchronized capture with structural backpressure.

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

**Mitigation**: nokhwa handles this internally. The camera thread runs on a dedicated OS thread (not a tokio async task), satisfying COM requirements. Already validated in the webcam test project.

**Mitigation**: nokhwa handles this internally. The camera thread runs on a dedicated OS thread (not a tokio async task), satisfying COM requirements. Already validated in the webcam test project.

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
      types.rs                       # RawFrame, FramePacket, CameraCommand, CameraEvent
      manager.rs                     # Camera lifecycle (open, configure, close, query)
      thread.rs                      # spawn_camera_thread, grab loop
      decoder.rs                     # Decoder thread (raw buffer → RGB)

    camera_group/
      mod.rs                         # Re-exports
      group.rs                       # CameraGroup: create, start, pause, unpause, close
      orchestrator.rs                # Sync gate, gatherer loop, recording boundaries
      channels.rs                    # All channel type definitions

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
| 1 | **`image` crate for JPEG, NOT `opencv`** | Pure Rust, no system dependency. The `opencv` crate requires an OpenCV installation — unacceptable for "it just works." `image` crate's JPEG encoder produces valid JPEGs; any visual difference from OpenCV's encoder is imperceptible. |
| 2 | **ffmpeg via `ffmpeg-sidecar`** | Battle-tested, produces files that play everywhere, handles every edge case. `ffmpeg-sidecar` auto-downloads the correct binary on first launch — zero user setup. The subprocess pipe pattern is already proven in the webcam test project. |
| 3 | **Best-practice high-precision monotonic clock** | Use the Rust equivalent of `time.perf_counter_ns()`: monotonic, highest available precision, not subject to wall-clock adjustments. Likely `libc::clock_gettime(CLOCK_MONOTONIC)` on Linux/macOS or `QueryPerformanceCounter` on Windows, wrapped in a cross-platform function. |
| 4 | **Range requests via `tower_http::ServeDir`** | Natively supported. If incompatible with dynamic path routing, manual `Range` header parsing. |
| 5 | **`utoipa` for OpenAPI/Swagger** | Derive macros on request/response structs. Swagger UI served at `/docs`. |
| 6 | **UUID with last 6 hex characters as group ID** | Matches Python behavior exactly. `uuid::Uuid::new_v4().to_string()[..6]` or equivalent truncation. |

---

## Milestones

| Milestone | Phases | Success Criterion |
|-----------|--------|-------------------|
| **M1: Camera Works** | 0-1 | Single camera grabs frames, displays preview, measures timestamps |
| **M2: Sync Works** | 2 | Two cameras in lockstep, zero drift over 5 minutes, grab spread < 1ms |
| **M3: Recording Works** | 3 | Two-camera synchronized video files, timestamps, statistics |
| **M4: JPEG Validated** | 5 | Live camera frames display in a browser from Rust WebSocket |
| **M5: API Complete** | 4, 6 | All 17 endpoints return responses matching Python output |
| **M6: Frontend Works** | 7 | Full frontend workflow succeeds against Rust backend |
| **M7: Shippable** | 8 | Single binary, documented, CI builds for all platforms |
