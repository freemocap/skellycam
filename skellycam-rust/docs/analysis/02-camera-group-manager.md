# Component #2: CameraGroupManager + CameraGroup + CameraManager

Status: **ANALYZED — stable reference artifact**

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

## What Changes in Rust

| Python Concept | Rust Equivalent | Key Difference |
|---------------|----------------|---------------|
| Module-level global singleton | `OnceLock<CameraGroupManager>` or an `Arc<CameraGroupManager>` passed via Axum state | `OnceLock` is thread-safe lazy init. No global variable footgun. |
| `get_or_create_camera_group_manager(app)` | `app.state` in Axum — constructor injection, no lazy init needed | Axum's `State` extractor provides typed, compile-time-checked dependency injection |
| Async PubSub wait loop for extracted configs | Thread joins a `sync_channel` recv — each camera thread sends config on startup channel | No async needed for thread coordination; threads return values via channels |
| Two-phase startup (spawn → wait → create SHM → notify) | Same logical flow, but simpler: spawn threads → recv configs from startup channel → allocate ring buffers on heap → send `Arc<RingBuffer>` handles to threads | Threads share address space — "shared memory" is just `Arc<T>`. No DTO/recreate pattern needed. |
| `multiprocessing.Value("q")` for recording boundaries | `Arc<AtomicI64>` — set during pause, read atomically by camera threads | Same semantics, simpler API, no multiprocessing import |
| PubSub for recording finished coordination | Each camera thread sends `RecordingFinished` on a oneshot channel; group collects all | `Vec<oneshot::Receiver<RecordingFinished>>` — simpler than PubSub for this one-shot pattern |
| PubSub for config updates | `mpsc::Sender<ConfigUpdate>` per camera, or `tokio::sync::broadcast` for multi-consumer | Direct typed channels replace topic-based string routing |
| `await_extracted_configs()` polling loop | Blocking `recv()` on a channel — the gatherer just waits for N configs | No polling needed; channels block until data arrives |
| `finalize_recording()` polling loop | Collect N `RecordingFinished` messages from oneshot channels or a shared mpsc | Same pattern, but the channels carry typed data, not arbitrary PubSub messages |
| Pydantic models for API types | `serde` derives on structs — same JSON shape, compile-time serialization | `#[derive(Serialize, Deserialize)]` replaces `BaseModel`. Same JSON output. |
| `CameraStatus` as 11 `multiprocessing.Value` booleans | `Arc<AtomicBool>` per flag OR a single `Arc<Mutex<CameraState>>` OR an `Arc<AtomicU16>` bitfield | Rust can pack flags into a single atomic, or use a Mutex for coherent state transitions |
| `CameraGroupState` Pydantic model | `#[derive(Serialize)] struct CameraGroupState` | Same JSON shape for API responses |

---

## Functionality That Must Be Preserved

1. **Camera group = top-level managed entity** — the API creates, reads, updates, destroys groups, not individual cameras
2. **Same HTTP endpoints with same JSON shapes** — frontend compatibility
3. **Two-phase startup** — spawn cameras, wait for all to report their actual config, then create shared structures
4. **Recording boundary coordination** — pause → set frame boundaries → unpause → all cameras cross boundary at same frame
5. **Config updates propagate to running cameras** — without stopping/restarting
6. **Multiple camera groups can coexist** — each with independent cameras, recording state, and lifecycle
7. **Recording finalization collects per-camera timestamps** — waits for all cameras to finish flushing
8. **Clean shutdown of individual groups** — close a group without affecting others
9. **Clean shutdown of all groups** — the global kill switch must still work
10. **Audio recording** — optional, started/stopped with video recording
