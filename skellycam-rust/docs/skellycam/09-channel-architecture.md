# Component #9: PubSub System → Rust Channels

Status: **AUDITED — updated for actual Rust implementation (2026-05-23)**

Files analyzed:
- `skellycam/core/ipc/pubsub/pubsub_abcs.py` — `PubSubTopicABC` base class (subscribe/publish/close)
- `skellycam/core/ipc/pubsub/pubsub_manager.py` — `PubSubTopicManager`, `TopicTypes` enum, singleton registry
- `skellycam/core/ipc/pubsub/pubsub_topics.py` — 7 topic types, 6 message types
- `skellycam/core/camera_group/camera_group_ipc.py` — `CameraGroupIPC`, topic subscriptions per group
- `skellycam/core/camera/camera_manager.py` — subscription creation for camera processes

---

## Part 1: What the Python PubSub Does

PubSub is the cross-process event bus. Since each camera runs in its own `multiprocessing.Process`, and the main FastAPI process is separate, processes can't share objects or call methods on each other. PubSub provides topic-based publish/subscribe using `multiprocessing.Queue` as the transport.

### Architecture

```
CameraGroupIPC (one per camera group)
  └── PubSubTopicManager
        └── topics: dict[TopicTypes, PubSubTopicABC]
              ├── UPDATE_CAMERA_SETTINGS → UpdateCamerasSettingsTopic
              ├── EXTRACTED_CONFIG      → DeviceExtractedConfigTopic
              ├── SHM_UPDATES           → SetShmTopic
              ├── RECORDING_INFO        → RecordingInfoTopic
              ├── RECORDING_FINISHED    → RecordingFinishedTopic
              ├── FRAMERATE             → FramerateTopic
              └── LOGS                  → LogsTopic

Each topic holds a list[multiprocessing.Queue] — one per subscriber.
publish(message) iterates all queues and puts the message.
get_subscription() creates a new Queue, appends it, and returns it to the caller.
```

### The "main process creates subscriptions" rule

```python
def get_subscription(self):
    if parent_process() is not None:
        raise RuntimeError("Subscriptions must be created in the main process and passed to children")
    sub = multiprocessing.Queue()
    self.subscriptions.append(sub)
    return sub
```

On Windows, `multiprocessing.Queue` objects must be created in the main process and passed to children before `Process.start()`. Children can `put()` and `get()` on pre-created queues but cannot create new ones. This is why `CameraGroupIPC` creates all subscriptions at construction time and passes them to `CameraManager.create()` which passes them to each camera process.

### Publish: broadcast to all subscribers

```python
def publish(self, message, overwrite=False):
    if not isinstance(message, self.message_type):
        raise TypeError(...)
    for subscription in self.subscriptions:
        if overwrite:
            while not subscription.empty():
                subscription.get()  # drain old messages
        subscription.put(message)
```

`overwrite=True` drains the queue first, so only the latest message is available. Used for framerate updates (only latest matters).

### Topic Catalog

| Topic | Direction | Message Type | Purpose | Consumed By |
|-------|-----------|-------------|---------|-------------|
| `UPDATE_CAMERA_SETTINGS` | Main → cameras | `UpdateCamerasSettingsMessage` | User changed camera config via API | `camera_loop_update_checks()` — reconfigures camera |
| `EXTRACTED_CONFIG` | Cameras → main | `DeviceExtractedConfigMessage` | Camera reports actual capabilities after opening | `await_extracted_configs()` — main collects all configs |
| `SHM_UPDATES` | Main → cameras | `SetShmMessage` | Shared memory DTOs (name + dtype) after allocation | Camera startup — recreates SHM from DTO |
| `RECORDING_INFO` | Main → cameras | `RecordingInfoMessage` | Recording started — camera should create VideoRecorder | `check_for_new_recording_info()` — creates VideoRecorder |
| `RECORDING_FINISHED` | Cameras → main | `RecordingFinishedMessage` | Camera finished recording — here's the metadata | `finalize_recording()` — collects all cameras' metadata |
| `FRAMERATE` | Cameras → main | `FramerateMessage` | Current framerate stats | `get_backend_framerate_updates()` — WebSocket relay |
| `LOGS` | Internal | `LogRecordModel` | Log records for WebSocket relay | Uses skellylogs queue, not multiprocessing.Queue |

### Runtime type checking

Every `publish()` call does `isinstance(message, self.message_type)`. Every subscription consumer does `isinstance(message, ExpectedType)` on receipt. This is necessary because `multiprocessing.Queue` is untyped — any Python object goes through pickle.

---

## Part 2: Why This Exists (Python-Specific Problems)

| Problem | Why It's a Problem in Python |
|---------|------------------------------|
| Separate process address spaces | The main process and camera processes have independent memory. You can't pass a reference or call a method across the boundary. |
| Windows spawn mode | `multiprocessing` on Windows uses `spawn` (not `fork`). The child imports the module fresh. All shared state must be passed explicitly before `Process.start()`. |
| No cross-process call stack | There's no way to call `camera.update_config()` from main. PubSub + polling in the camera loop is the workaround. |
| `multiprocessing.Queue` is untyped | Messages are pickled bytes. Type errors are runtime `isinstance()` checks, not compile-time. |
| Multiprocessing overhead | Every message goes through pickle serialization + OS pipe. Overhead scales with message size (problematic for frame metadata). |
| Runtime enforcement of "main process creates queues" | The check `parent_process() is not None` catches bugs that would only manifest on Windows. |

---

## Part 3: What Changes in Rust

All of this goes away. Threads share the heap. Channels replace queues. The type system replaces `isinstance()`.

### Topic-by-Topic Mapping

#### UPDATE_CAMERA_SETTINGS → `mpsc::Sender<ControlCommand>`

In Python: main publishes to a multiprocessing.Queue, camera loop polls it every iteration.

In Rust: each camera's control loop has an `mpsc::Receiver<ControlCommand>` paired with a sender held by the CameraGroup. Commands are sent directly — no topic manager, no multiprocessing, no polling.

```rust
enum ControlCommand {
    UpdateSettings(CameraConfig),
    Shutdown,
}

// CameraGroup sends:
camera_control_senders[&camera_id].send(ControlCommand::UpdateSettings(new_config)).await?;

// Camera control loop receives:
loop {
    tokio::select! {
        command = control_receiver.recv() => {
            match command {
                Some(ControlCommand::UpdateSettings(config)) => { /* reconfigure */ }
                Some(ControlCommand::Shutdown) => break,
                None => break, // channel closed
            }
        }
        frame = camera.frame() => { /* normal frame processing */ }
    }
}
```

`tokio::select!` is the key difference from Python. Instead of polling the PubSub queue at the top of every loop iteration (which adds latency), `select!` wakes immediately when a command arrives. No busy-wait, no 10ms poll interval.

#### EXTRACTED_CONFIG → `mpsc::Sender<CameraConfig>`

In Python: camera publishes config, main polls subscription queue in `await_extracted_configs()`.

In Rust: camera thread sends config through a oneshot or mpsc channel during startup. CameraGroup receives.

```rust
// Camera thread startup:
let (config_sender, config_receiver) = mpsc::channel(1);

thread::spawn(move || {
    let camera = Camera::open(...);
    let config = camera.extract_config();
    config_sender.send(config).unwrap();
    // ... enter main loop ...
});

// CameraGroup startup:
let config = config_receiver.recv().unwrap(); // blocks until camera sends
```

#### SHM_UPDATES → NOT NEEDED

In Python: after allocating shared memory, main publishes SHM DTOs so camera processes can `recreate()` the buffers.

In Rust: no shared memory needed. Threads share the heap. The "buffer" is an `Arc<Vec<u8>>` or the channel receiver handle itself.

#### RECORDING_INFO → `mpsc::Sender<RecordingInfo>`

Same pattern as UPDATE_CAMERA_SETTINGS. CameraGroup sends RecordingInfo to each camera's control loop channel.

```rust
// Instead of pubsub.publish(RecordingInfoMessage(recording_info))
// Just send to each camera's control channel:
for sender in &camera_control_senders {
    sender.send(ControlCommand::StartRecording(recording_info.clone())).await?;
}
```

#### RECORDING_FINISHED → `mpsc::Sender<Vec<RecordedFrameMetadata>>`

In Python: camera process publishes metadata. Main polls. Must wait for all cameras.

In Rust: each recorder thread sends metadata to a collector channel. CameraGroup receives from all cameras.

```rust
// One channel per camera for recording finished:
let (finished_sender, finished_receiver) = mpsc::channel(1);

// Recorder thread:
finished_sender.send(frame_metadatas).await?;

// CameraGroup finalization:
let mut all_metadata = Vec::new();
for receiver in &recording_finished_receivers {
    all_metadata.push(receiver.recv().await?);
}
```

#### FRAMERATE → `watch::Sender<CurrentFramerate>`

Only the latest value matters. `watch` is purpose-built for this.

```rust
let (framerate_sender, framerate_receiver) = watch::channel(CurrentFramerate::default());

// Camera loop (or gatherer):
framerate_sender.send_replace(new_framerate);

// WebSocket task:
loop {
    framerate_receiver.changed().await?;
    let framerate = framerate_receiver.borrow();
    // forward to frontend via WebSocket JSON
}
```

#### LOGS → `tracing` + custom WebSocket layer

Python uses skellylogs with a queue handler. In Rust, use the `tracing` ecosystem:

```rust
use tracing_subscriber::layer::SubscriberExt;

// A tracing layer that sends log records to a broadcast channel
let (log_sender, _) = broadcast::channel::<LogRecord>(256);

// WebSocket task subscribes:
let log_receiver = log_sender.subscribe();
loop {
    let record = log_receiver.recv().await?;
    websocket.send(Message::Text(serde_json::to_string(&record)?)).await?;
}
```

### Structural Simplification

The entire `PubSubTopicABC` base class, `PubSubTopicManager` singleton registry, `TopicTypes` enum, 6 message wrapper classes, 7 topic classes, and all the `isinstance()` checks collapse to:

```rust
// Channels held by CameraGroup, passed to threads at spawn time.
pub struct CameraGroupChannels {
    /// Send commands to each camera's control loop
    pub camera_control_senders: HashMap<String, mpsc::Sender<ControlCommand>>,
    /// Receive framerate updates (latest only)
    pub framerate_receiver: watch::Receiver<CurrentFramerate>,
    /// Receive recording finished metadata from each camera
    pub recording_finished_receivers: Vec<mpsc::Receiver<Vec<RecordedFrameMetadata>>>,
    /// Broadcast log records to WebSocket tasks
    pub log_sender: broadcast::Sender<LogRecord>,
}
```

That's ~20 lines of channel definitions replacing ~300 lines of PubSub infrastructure.

---

## Functionality That Must Be Preserved

1. **Camera settings update propagating to all cameras** — settings change on one API call, all cameras reconfigure
2. **Startup config extraction** — cameras report actual capabilities before main proceeds
3. **Recording info broadcast to all cameras** — all cameras start recording simultaneously
4. **Recording finished collection from all cameras** — main waits for all cameras to finish
5. **Framerate stats flowing to WebSocket** — latest-value semantics (old values discarded)
6. **Log records flowing to WebSocket** — non-blocking, lossy under backpressure
7. **Topics scoped to camera group** — messages don't leak between groups (channels are owned by the group, so this is automatic)
8. **Clean shutdown** — closing a topic closes all subscriptions (channels drop when the group is dropped)

---

## Actual Channel Architecture

The channel-based approach was implemented as planned, but with different concrete types:

### Topic-by-Topic — Planned vs Actual

| Topic | Planned Channel | Actual Channel | Notes |
|-------|----------------|----------------|-------|
| `UPDATE_CAMERA_SETTINGS` | `mpsc::Sender<ControlCommand>` | `mpsc::Sender<CameraCommand>` | Matches plan. `CameraCommand::Configure { config }` variant. |
| `EXTRACTED_CONFIG` | `mpsc::Sender<CameraConfig>` | NOT NEEDED | Configs are written to `Arc<Mutex<CameraConfig>>` by camera threads directly. |
| `SHM_UPDATES` | NOT NEEDED | NOT NEEDED | Threads share address space — no SHM DTOs. |
| `RECORDING_INFO` | `mpsc::Sender<RecordingInfo>` | `mpsc::Sender<DispatcherCommand::StartRecording>` | Recording commands go through dispatcher, not directly to cameras. |
| `RECORDING_FINISHED` | `mpsc::Sender<Vec<RecordedFrameMetadata>>` | `oneshot::Sender<RecordingSummary>` | Stop recording gets a oneshot response from the recording thread via dispatcher. |
| `FRAMERATE` | `watch::Sender<CurrentFramerate>` | `FramerateTracker` in WebSocket handler | FPS computed in the WebSocket loop itself from camera_fps field in FrontendPayload. |
| `LOGS` | `tracing` + `broadcast::channel` | `tracing` + `broadcast::channel` → `mpsc` bridge | Matches plan. `LogRelayLayer` → `broadcast` → tokio mpsc bridge in WS handler. |

### Channel Types (Actual)

All camera pipeline channels use `std::sync::mpsc` (OS threads), not `tokio::sync::mpsc`:

| Channel | Type | Capacity | Use |
|---------|------|----------|-----|
| Camera command | `mpsc::channel()` | unbounded | `CameraCommand::Shutdown` / `Configure` |
| Camera event | `mpsc::channel()` | unbounded | `CameraEvent::Ready` / `Error` |
| Camera → Gatherer frames | `sync_channel()` | 1 | Backpressure: camera blocks until gatherer consumes |
| Gatherer → Dispatcher | `mpsc::channel()` | unbounded | Gatherer must never block |
| Gatherer updates | `mpsc::channel()` | unbounded | `GathererUpdate::AddCamera` / `RemoveCamera` |
| Dispatcher control | `mpsc::channel()` | unbounded | `DispatcherCommand::StartRecording` / `StopRecording` / `Shutdown` / `UpdateConfigs` |
| Recording frames | `mpsc::channel()` | unbounded | Dispatcher → recording thread |
| Stop recording response | `mpsc::channel()` | 1 | Oneshot: dispatcher → caller |

Only the WebSocket handler uses `tokio::sync::mpsc` (for the log relay bridge).

### Why `std::sync::mpsc`, Not `tokio::sync::mpsc`

The camera pipeline runs on OS threads (`std::thread::spawn`), not tokio tasks. `std::sync::mpsc` is the natural choice for OS threads — zero async overhead, no runtime dependency. The tokio runtime is only used for the HTTP/WebSocket server layer.

### Sync Mechanism: BreakableBarrier

Not mentioned in the original PubSub analysis because Python has no equivalent. The `BreakableBarrier` is the synchronization primitive that replaces `should_grab_by_id()` polling:

```rust
// sync_utils.rs
pub struct BreakableBarrier { ... }
impl BreakableBarrier {
    pub fn new(total: usize) -> Self;
    pub fn wait(&self) -> bool;         // true = normal release, false = barrier broken
    pub fn break_barrier(&self);        // release all waiters, subsequent wait() returns false
    pub fn set_total(&self, total: usize); // dynamic participant count change
}
```

## What's Completely Eliminated (Accurate)

| Python Artifact | Why Eliminated |
|----------------|----------------|
| `PubSubTopicABC` base class | Channels are the abstraction — no inheritance needed |
| `PubSubTopicManager` singleton | Channels are fields on CameraGroup |
| `TopicTypes` enum + 7 concrete topic classes | Channel type parameters distinguish message types |
| `TopicMessageABC` + 6 message wrapper classes | Rust enum variants carry data directly |
| `multiprocessing.Queue` for every subscription | Rust channels are the primitive |
| `isinstance()` type checks at publish and consume | Rust generics enforce types at compile time |
| `parent_process() is not None` guard | No process boundary — threads share creation context |
| `overwrite=True` drain loop | `watch::send_replace()` is O(1) |
| Pickle serialization of all messages | Messages stay on the heap — `Arc` ref bump, not serialization |
| Polling subscription queues in hot loop | `tokio::select!` is event-driven |
| `create_camera_group_pubsub_manager()` global registry | Channels are created inside `CameraGroup::new()` |
