# Component #2: CameraGroupManager + CameraGroup + CameraManager

Status: **AUDITED — updated for actual Rust implementation (2026-05-23)**

Files analyzed:
- `skellycam/core/camera_group/camera_group_manager.py` — CameraGroupManager, singleton factory
- `skellycam/core/camera_group/camera_group.py` — CameraGroup, await_extracted_configs, finalize_recording
- `skellycam/core/camera/camera_manager.py` — CameraManager (creates CameraWorkers + CameraOrchestrator)
- `skellycam/api/http/cameras/camera_router.py` — HTTP endpoints
- `skellycam/api/routers.py` — router list
- `skellycam/core/camera_group/camera_status.py` — CameraStatus flags

---

## What It Does

Three-layer hierarchy that manages the complete lifecycle of camera groups:

```
CameraGroupManager  ← singleton, owns all groups, routes API commands
    │
    └── CameraGroup  ← owns IPC, SharedMemory, CameraManager; one per group
            │
            └── CameraManager  ← creates CameraWorkers + CameraOrchestrator from configs
```

### Layer 1: CameraGroupManager (singleton)

**Single responsibility**: Registry of camera groups. Routes API commands to the correct group.

- `camera_groups: dict[GroupId, CameraGroup]` — the registry
- `create_and_start_camera_group(configs)` — creates a CameraGroup, subscribes to its framerate topic, starts it, stores it
- `create_or_update_camera_group(configs)` — if camera IDs match an existing group → update settings; otherwise → create new group
- `get_camera_group(id)` — lookup by ID
- `close_all_camera_groups()` — iterate all groups, close each, clear dict
- `start_recording_all_groups()` / `stop_recording_all_groups()` — fan-out to all groups
- `pause_all_groups()` / `unpause_all_groups()` / `pause_unpause_all_groups()` — fan-out
- `get_latest_frontend_payloads(if_newer_than)` — poll each group's shared memory, create bytearray payloads
- `get_backend_framerate_updates()` — drain framerate PubSub subscriptions
- `get_latest_performance_data()` — extract per-camera frame lifecycle stats
- `find_camera_group_by_camera_ids(ids)` — reverse lookup

**Singleton factory**: `get_or_create_camera_group_manager(app: FastAPI)` — stores the singleton in a module-level global `_CAMERA_GROUP_MANAGER`. Lazily initialized on first call.

### Layer 2: CameraGroup

**Single responsibility**: Owns one synchronized multi-camera group. Manages its IPC, shared memory, recording lifecycle, and frontend payloads.

**Creation** (`CameraGroup.create`):
1. `validate_camera_configs(configs)` — ensure all camera IDs are unique, etc.
2. `CameraGroupIPC.create(global_kill_flag, heartbeat_timestamp)` — creates PubSub, subscriptions, group ID
3. `CameraManager.create(ipc, worker_registry, camera_configs)` — creates CameraStatus dict, CameraOrchestrator, CameraWorkers

**Startup** (`CameraGroup.start()`):
1. Call `cameras.start()` — spawns all camera processes (with 250ms stagger on Windows)
2. `await_extracted_configs(ipc, requested_configs)` — wait for each camera worker to publish its `DeviceExtractedConfigMessage` via PubSub (camera opens, queries actual resolution/capabilities, sends them back)
3. `CameraGroupSharedMemory.create(extracted_configs, timebase_mapping)` — allocate shared memory sized for actual camera resolutions
4. `ipc.publish_shm_message(shm_dto)` — send shared memory DTO to all camera workers so they can `recreate()` it in their processes
5. Update `self.configs` with extracted configs (actual, not requested)

**Recording lifecycle**:
- `start_recording(recording_info)` — pause all cameras, set `first_recording_frame_number = current_frame + 3`, publish RecordingInfoMessage, optionally start AudioRecorder, unpause
- `stop_recording()` — pause all cameras, set `last_recording_frame_number = current_frame + 3`, stop audio, unpause, wait for all cameras to publish `RecordingFinishedMessage`, run `RecordingFinalizer`

**Frontend payloads**:
- `get_latest_frames()` → `shm.get_latest_multiframe()`
- `get_latest_frontend_payload(if_newer_than)` → `create_frontend_payload(latest_frames)` → `(frame_number, timestamp, bytearray)`
- `get_frontend_payload_by_frame_number(n)` — for playback, reads specific frame from ring buffer

**Shutdown**: stop recording if active, stop audio, set `ipc.should_continue = False`, close cameras (escalating shutdown), unlink+close shared memory.

### Layer 3: CameraManager

**Single responsibility**: Creates the orchestrator and camera workers from configs. Delegates pause/unpause/close to the orchestrator.

- Creates `CameraStatus` dict (one per camera — all `multiprocessing.Value` flags)
- Creates `CameraOrchestrator.from_statuses(statuses)`
- Creates `CameraWorker` per camera via `CameraWorker.create(...)` — each gets references to IPC, orchestrator, config, and PubSub subscriptions
- `start()` — staggered process spawn (250ms on Windows)
- `close()` — 3-phase escalating shutdown (wait → SIGTERM → SIGKILL), same pattern as WorkerRegistry

### HTTP API Surface

All endpoints are under `/skellycam/camera/`:

| Method | Path | Handler | What it does |
|--------|------|---------|--------------|
| POST | `/detect` | `cameras_detect_endpoint` | Enumerate USB cameras |
| GET | `/microphone/detect` | `microphone_detect_endpoint` | Enumerate mics |
| POST | `/group/apply` | `camera_group_apply_post_endpoint` | Create or update a camera group |
| POST | `/group/all/record/start` | `start_recording` | Start recording all groups |
| GET | `/group/all/record/stop` | `stop_recording` | Stop recording, return stats |
| DELETE | `/group/close/all` | `close_all_camera_groups` | Shutdown all groups |
| GET | `/group/all/pause_unpause` | `pause_camera_groups` | Toggle pause |

Additional routers: `/ws` (WebSocket), `/playback` (playback).

### Request/Response Types (Pydantic models)

- `CameraGroupCreateRequest` — `{ camera_configs: dict[CameraIdString, CameraConfig] }`
- `CreateCameraGroupResponse` — `{ group_id, camera_configs }`
- `StartRecordingRequest` — `{ recording_name, recording_directory, mic_device_index }`
- `StopRecordingResponse` — `{ recording_name, recording_path, number_of_cameras, number_of_frames, total_duration_sec, mean_framerate, mean_inter_camera_sync_ms, framerate_stats, frame_duration_stats, inter_camera_grab_range_ms_stats }`

---

## Python-Specific Problems This Architecture Solves

| Problem | Python Solution | Why It Exists |
|---------|----------------|---------------|
| Singleton across HTTP requests | Module-level global `_CAMERA_GROUP_MANAGER` + `get_or_create_camera_group_manager(app)` | FastAPI has no built-in singleton DI; route handlers are stateless functions |
| Config extracted in separate process | Async PubSub wait loop — each camera publishes `DeviceExtractedConfigMessage`, group waits for all | Camera opens in child process; extracted config (actual resolution, supported controls) must cross process boundary |
| Shared memory must be created after config known | Two-phase startup: 1) spawn processes, 2) wait for extracted configs, 3) create SHM, 4) publish DTO to children | SHM size depends on actual frame size, which depends on camera capabilities discovered at open time |
| Shared memory must be accessible across processes | `SharedMemory` created in main process, DTO passed via PubSub, children `recreate()` from DTO | Each process has separate address space; SHM name + dtype is the cross-process handle |
| Recording boundary coordination | `first_recording_frame_number` / `last_recording_frame_number` as `multiprocessing.Value("q")`, set while cameras are paused | Cameras run in separate processes; recording boundaries must be communicated via shared memory |
| Frame count alignment at recording start/stop | Pause all cameras → set boundary values → unpause. +3 frame offset ensures all cameras see the same boundary | Without pausing, cameras could be at different frame numbers when boundaries are set |
| Wait for recording to finish across processes | `finalize_recording()` — async loop waiting for each camera to publish `RecordingFinishedMessage` via PubSub | Each camera flushes its own VideoWriter + timestamps; main process must wait for all |
| Config updates across running cameras | Publish `UpdateCamerasSettingsMessage` via PubSub; cameras check their subscription queue at loop start | Config changes must reach the right camera process; PubSub provides topic-based routing |
| Camera process crash during recording | Error handling in `close()`: check if recording in progress → try to stop → then close. `atexit` on child processes | Must preserve recorded data even during crash shutdown |

---

## What Was Actually Built

### Layer 1: CameraGroupManager

Located in `camera_group_manager/mod.rs`. Pure Rust, no Python dependency.

```rust
pub struct CameraGroupManager {
    groups: HashMap<String, CameraGroup>,
}
```

- `create_or_update_group(configs, group_id)` — creates a `CameraGroup`, calls `start()`, stores it
- `close_group(id)` / `close_all_groups()` — shutdown and remove
- `get_group(id)` / `get_group_mut(id)` — lookup by ID
- `to_state_dict()` — serializable snapshot for API responses
- `Drop` impl calls `close_all_groups()` if any groups remain

Wrapped in `Mutex<CameraGroupManager>` inside `Arc<AppState>` — not a module-level global. The "singleton" property emerges from having one `AppState` passed to the Axum router.

### Layer 2: CameraGroup

Located in `camera_group/camera_group.rs`. The central orchestrator.

**Creation** (`CameraGroup::new(configs)`):
1. Generates a 6-char UUID group ID
2. Stores configs in `HashMap<String, CameraGroupConfig>`
3. State = `Created`

**Startup** (`CameraGroup::start()`):
1. Pause all cameras (set `paused = true`)
2. Create `BreakableBarrier` with count = camera_count + 1
3. Spawn each camera via `Camera::start(identity, config, barrier, paused, 0)`
4. Failed spawns are logged and skipped — the group continues with remaining cameras
5. Wait for each camera to send `Ready` via `wait_until_ready(timeout)`
6. Failed stabilizations are logged and skipped
7. Correct barrier count to actual camera count + 1
8. Take each camera's frame receiver via `take_frame_receiver()`
9. Spawn gatherer thread with frame receivers + barrier
10. Spawn dispatcher thread with gatherer channel receiver
11. Unpause → `Streaming` state

**No two-phase startup with extracted configs.** Cameras self-configure during `Camera::start()` — `find_best_mjpg()` negotiates format, writes actual resolution/framerate to `Arc<Mutex<CameraConfig>>`. No DTO/recreate pattern because threads share address space.

**Recording**: `start_recording(params)` sends `DispatcherCommand::StartRecording` to the dispatcher thread. `stop_recording()` sends `StopRecording` and receives `RecordingSummary` via a oneshot channel. No pause-before-record protocol.

**Frontend**: `latest_frontend_payload()` reads from `Arc<Mutex<Option<FrontendPayload>>>` updated by the dispatcher. `latest_raw_frames()` provides per-camera JPEGs for on-demand decode.

**Shutdown**: Sends shutdown commands to all cameras, sends `DispatcherCommand::Shutdown`, breaks the barrier, joins all threads.

### Layer 3: Camera (replaces CameraManager)

There is no separate `CameraManager` struct. Each `Camera` is a handle to a dedicated OS thread:

```rust
pub struct Camera {
    command_sender: mpsc::Sender<CameraCommand>,
    frame_receiver: Option<mpsc::Receiver<FramePacket>>,
    event_receiver: mpsc::Receiver<CameraEvent>,
    thread_handle: Option<JoinHandle<()>>,
    identity: CameraIdentity,
    config: Arc<Mutex<CameraConfig>>,
}
```

- `start()` — creates COM context, opens stream, stabilizes, spawns capture thread
- `configure(config)` — sends `Configure` command to running camera thread
- `try_recv_frame()` — non-blocking frame poll
- `shutdown()` — sends `Shutdown` command, joins thread

### CameraStatus — radically simplified

```rust
pub struct CameraStatus {
    pub camera_name: String,
    pub camera_index: i32,
    pub device_path: String,
    pub config: CameraConfig,
}
```

No 11 boolean flags. A single `paused: Arc<AtomicBool>` shared across all cameras in a group replaces `is_paused`, `should_pause`, `should_close`, etc. The `Ready`/`Error` event channel replaces `connected`, `error`, `closing`, `closed`.

---

## Functionality Preserved

1. **Camera group = top-level managed entity** — the API creates, reads, updates, destroys groups, not individual cameras
2. **Same HTTP endpoints with same JSON shapes** — frontend compatibility maintained
3. **Config updates propagate to running cameras** — via `Camera::configure()` which sends `Configure` command to the camera thread
4. **Multiple camera groups can coexist** — `CameraGroupManager` holds a `HashMap<String, CameraGroup>`
5. **Clean shutdown of individual groups** — `close_group(id)` shuts down one group without affecting others
6. **Clean shutdown of all groups** — `close_all_groups()` + `Drop` impl

## Functionality Changed (by design)

- **Two-phase startup** — No extracted configs phase. Cameras self-configure via `find_best_mjpg()` during `Camera::start()`. Results written to `Arc<Mutex<CameraConfig>>` visible to all threads.
- **Recording boundary coordination** — No pause-before-record with +3 frame offset. Recording starts/stops on-the-fly via dispatcher commands.
- **Recording finalization** — Simplified to collecting per-camera metadata and file paths from the recording thread.
- **Audio recording** — Not implemented (future scope).
