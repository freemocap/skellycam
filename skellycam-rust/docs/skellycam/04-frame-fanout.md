# Component #4: Ring Buffer → Broadcast Fan-Out + Frontend Payload + WebSocket

Status: **AUDITED — updated for actual Rust implementation (2026-05-23)**

Files analyzed:
- `skellycam/core/ipc/shared_memory/ring_buffer_shared_memory.py` — SharedMemoryRingBuffer
- `skellycam/core/ipc/shared_memory/camera_group_shared_memory.py` — CameraGroupSharedMemory
- `skellycam/core/ipc/shared_memory/shared_memory_element.py` — SharedMemoryElement (low-level)
- `skellycam/core/ipc/shared_memory/shared_memory_number.py` — SharedMemoryNumber (cursor)
- `skellycam/core/types/frontend_payload_bytearray.py` — create_frontend_payload, binary protocol
- `skellycam/api/websocket/websocket_server.py` — WebsocketServer, image relay loop
- `skellycam/api/websocket/websocket_connect.py` — WebSocket endpoint

---

## What It Does

Three layers that bridge from captured frames to the frontend:

### Layer 1: Per-Camera Ring Buffer (Python: `SharedMemoryRingBuffer`)

Each camera writes frames into its own shared memory ring buffer. Two cursors:
- `last_written_index` — updated by the camera thread after each write
- `last_read_index` — updated by the consumer

Key operations:
- `put_data(data, overwrite_allowed=True)` — writes to next slot. If `overwrite_allowed` and the slot would overwrite unread data, it overwrites anyway (hot loop protection).
- `get_latest_data()` — returns most recent frame. Does NOT advance `last_read_index`. Used by "show me the latest" consumers.
- `get_data_by_index(index)` — reads a specific frame by its logical index. Used by the gatherer to assemble multi-frames.
- `get_next_data()` — sequential consumption, advances `last_read_index`. Used by the recorder.

The DTO pattern: `SharedMemoryRingBufferDTO` carries the shared memory name + dtype so another process can `recreate()` it.

### Layer 2: Multi-Frame Assembly (Python: `CameraGroupSharedMemory`)

Wraps one ring buffer per camera. Key operation:

```python
def get_latest_multiframe(self):
    target_frame_number = self.latest_multiframe_number  # min() across all cameras
    frames = {
        camera_id: camera_shm.get_data_by_index(index=target_frame_number)
        for camera_id, camera_shm in self.camera_shms.items()
    }
    assert len(set(frame_numbers)) == 1  # all cameras at same frame number
    return frames
```

The "multi-frame" is a dict of per-camera numpy recarrays, all at the same frame number. The frame number is the minimum across all cameras (the gatherer's floor).

### Layer 3: Frontend Payload Encoding (Python: `create_frontend_payload`)

Converts multi-frame recarrays into a compact binary bytearray for WebSocket transmission.

**Binary protocol layout** (exact byte format the frontend expects):

```
[PAYLOAD_HEADER]
  message_type:    u1 = 0
  frame_number:    i8 (little-endian)
  number_of_cameras: i4

[FRAME_HEADER for camera 0]
  message_type:    u1 = 1
  frame_number:    i8
  camera_id:       S16 (fixed 16 bytes, UTF-8)
  camera_index:    i4
  image_width:     i4
  image_height:    i4
  color_channels:  i4
  jpeg_string_length: i4

[JPEG bytes for camera 0]  ← variable length, specified by jpeg_string_length

[FRAME_HEADER for camera 1]
  ...same structure...

[JPEG bytes for camera 1]

[PAYLOAD_FOOTER]
  message_type:    u1 = 2
  frame_number:    i8
  number_of_cameras: i4
```

**Processing per camera** (inside `create_frontend_payload`):
1. Extract grab timestamp midpoint: `mean(pre_grab_ns, post_grab_ns)`
2. Rotate image (if `rotation != -1`) via `cv2.rotate()`
3. Resize to 50% of native resolution (or custom display size) via `cv2.resize(INTER_LINEAR)`
4. JPEG encode at quality 80 via `cv2.imencode('.jpg')`
5. Assemble frame header + JPEG bytes into bytearray

Performance optimization: a reusable global `_reusable_bytes_payload` bytearray is pre-allocated at ~1MB per camera and reused across calls.

### Layer 4: WebSocket Server (Python: `WebsocketServer`)

Four concurrent async tasks on each WebSocket connection:

| Task | What it does | Rate |
|------|-------------|------|
| `_frontend_image_relay` | Polls `get_latest_frontend_payloads()` every 10ms, sends bytes. Tracks backpressure via frontend frameNumber confirmations. Computes server/display framerates. | 10ms poll, throttled by frontend ack |
| `_logs_relay` | Drains skellylogs queue, sends log records as JSON | Poll-driven |
| `_client_message_handler` | Receives JSON from frontend: `frameNumber` (backpressure ack), `displayImageSizes`. Also handles ping/pong. | Event-driven |
| `_app_state_sender` | Sends serialized CameraGroupManager state every 1s (only when changed) | 1s poll |

**Backpressure mechanism**: The frontend sends a JSON message `{"frameNumber": N}` to acknowledge it has displayed frame N. The server tracks `last_sent_frame_number` and `last_received_frontend_confirmation`. If the gap exceeds 1000 frames, it logs a warning. If the frontend hasn't acknowledged the last sent frame, the server skips sending (waits for the frontend to catch up). This is a cooperative backpressure protocol over WebSocket.

**Framerate tracking**: Two independent trackers per camera group:
- **Server framerate**: computed from `(frame_number, capture_timestamp_ns)` pairs — the true camera capture rate
- **Display framerate**: computed from WebSocket send times — what the UI actually receives

---

## Python-Specific Problems This Architecture Solves

| Problem | Python Solution | Why It Exists |
|---------|----------------|---------------|
| Frames cross process boundaries | Shared memory ring buffer — processes map the same physical pages | Processes have separate address spaces |
| Ring buffer cursor management | Two `multiprocessing.Value("q")` cursors (read/write) in shared memory | Cursors must be visible to both producer and consumer processes |
| Frame data is large (multi-MB) | Zero-copy via shared memory — numpy recarray sits in SHM, consumer reads directly | Copying frame data through pipes/queues would be too slow |
| DTO pattern for SHM handles | `to_dto()` / `recreate(dto)` — serialize SHM name + dtype, pass via PubSub, reconstruct in child | Each process must independently map the shared memory region by name |
| Overwrite semantics protect hot loop | `overwrite_allowed=True` — if consumer falls behind, old frames silently overwritten | Streaming consumer must never block the camera producer |
| JPEG encoding is expensive | Done in main process (WebSocket task), not in camera process | Keeps the hot loop thin |
| Reusable bytearray avoids GC | Global `_reusable_bytes_payload` pre-allocated, resized on demand | Python GC pauses would cause jitter in the streaming loop |
| Async send lock | `asyncio.Lock` serializes all WebSocket writes | The `websockets` library doesn't support concurrent writes |
| Backpressure from frontend | Cooperative: frontend sends `frameNumber` acks, server skips if unacknowledged | WebSocket has no built-in flow control |
| msgspec for fast JSON | `msgspec.json.Encoder` used instead of `json.dumps` for framerate/log messages | msgspec is 3-5x faster than stdlib json for struct serialization |

---

## What Was Actually Built

### The Dispatcher Fan-Out Pattern

The planned gatherer→broadcast fan-out was NOT implemented. Instead, a **dispatcher thread** sits between the gatherer and all downstream consumers:

```
Gatherer ──unbounded mpsc──→ Dispatcher ──┐
                                │          ├── Arc<Mutex<Option<FrontendPayload>>>  ← WS polls
                                │          ├── Arc<Mutex<Option<Vec<RawFrame>>>>     ← on-demand decode
                                │          └── Recording thread (via channel)         ← only when recording
```

The dispatcher `try_recv()`s from the gatherer channel (never blocking), encodes the frontend payload, stores it in a shared slot, and — if recording is active — forwards per-camera JPEGs to the recording thread.

### Channel Types (Actual)

| Connection | Channel Type | Behavior | Why |
|-----------|-------------|----------|-----|
| **Camera → Gatherer** | `sync_channel(1)` | Blocking send, capacity 1 | Backpressure: camera blocks if gatherer hasn't consumed previous frame. After send, camera enters barrier. |
| **Gatherer → Dispatcher** | `mpsc::channel()` (unbounded) | Non-blocking send, every frame | Gatherer must never block — it holds the barrier. Dispatcher keeps up or the channel grows. |
| **Dispatcher → Recorder** | `mpsc::channel()` (unbounded) | Non-blocking send, every frame | Recording thread has its own ffmpeg pacing. |
| **Dispatcher → Frontend** | `Arc<Mutex<Option<FrontendPayload>>>` | Shared slot, write + clone on read | WebSocket polls `latest_frontend_payload()` every 10ms. No channel — just an atomic slot swap. |
| **CameraGroup → Gatherer** | `mpsc::channel()` | `GathererUpdate::AddCamera`/`RemoveCamera` | Dynamic camera set changes. Drained via `try_recv()` at top of gatherer loop. |

### WebSocket: Polling, Not Watch

The WebSocket server does NOT use `tokio::sync::watch`. Instead, it polls `CameraGroup::latest_frontend_payload()` every 10ms:

```rust
loop {
    let payload = manager.get_group(group_id)
        .and_then(|g| g.latest_frontend_payload());
    if let Some(payload) = payload {
        if payload.frame_number > last_frame_number {
            socket.send(Message::Binary(payload.jpeg_bytes.into())).await?;
            last_frame_number = payload.frame_number;
        }
    }
    tokio::time::sleep(Duration::from_millis(10)).await;
}
```

No `frameNumber` backpressure from frontend — frames are sent as fast as the WebSocket can push them. If the frontend falls behind, TCP backpressure applies naturally.

### JPEG Processing: MJPEG Passthrough

The planned "decode BGR → resize to 50% → JPEG encode at quality 80" pipeline is NOT used for the primary MJPEG path. Instead:
- **MJPEG frames** pass through the pipeline as raw bytes — no decode, no resize, no re-encode
- Only lossless JPEG rotation is applied in the dispatcher via `rotate_jpeg_lossless()` (using turbojpeg `tjTransform`)
- The RGB path (`resize_rgb` + `jpeg_encode_rgb` at quality 80) exists only as a fallback for non-MJPEG cameras

### WebSocket Binary Protocol Must Be Preserved Exactly

The frontend JavaScript parses this exact byte layout. The Rust implementation must produce bit-identical output:

```rust
// Equivalent to FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE
#[repr(C, packed)]
struct PayloadHeader {
    message_type: u8,        // 0
    frame_number: i64,       // little-endian
    number_of_cameras: i32,  // little-endian
}

// Equivalent to FRONTEND_FRAME_HEADER_DTYPE
#[repr(C, packed)]
struct FrameHeader {
    message_type: u8,        // 1
    frame_number: i64,
    camera_id: [u8; 16],     // fixed 16 bytes, UTF-8
    camera_index: i32,
    image_width: i32,
    image_height: i32,
    color_channels: i32,
    jpeg_string_length: i32,
}
```

Processing per camera (Rust equivalent):
1. Compute grab timestamp midpoint
2. Rotate image (if rotation != -1) via `image::imageops::rotate90` etc.
3. Resize to 50% (or custom display size) via `image::imageops::resize` with `FilterType::Triangle` (≈ INTER_LINEAR)
4. JPEG encode at quality 80 via `image::codecs::jpeg::JpegEncoder`
5. Write header bytes + JPEG bytes into a pre-allocated `Vec<u8>`

### WebSocket Server Architecture (Rust)

In Python, the WebSocket server uses 4 concurrent async tasks sharing state on `self`. In Rust with Axum:

```rust
// Axum WebSocket handler
async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_ws(socket, state))
}

async fn handle_ws(mut socket: WebSocket, state: Arc<AppState>) {
    let (mut sender, mut receiver) = socket.split();

    // Task 1: Image relay
    let ws_rx = state.ws_watch_rx.clone(); // watch::Receiver
    let relay = tokio::spawn(async move {
        loop {
            ws_rx.changed().await?;  // wait for new payload
            let payload = ws_rx.borrow();
            let bytes = encode_frontend_payload(&payload);
            sender.send(Message::Binary(bytes.into())).await?;
        }
    });

    // Task 2: Client message handler
    let msg_handler = tokio::spawn(async move {
        while let Some(msg) = receiver.next().await {
            match msg {
                Ok(Message::Text(text)) => {
                    // Parse frameNumber, displayImageSizes from JSON
                }
                Ok(Message::Ping(_)) => { /* pong */ }
                _ => break,  // Close or error
            }
        }
    });

    // Task 3: State sender (every 1s)
    // Task 4: Log relay
    // ...
}
```

The async send lock isn't needed in Axum — `split()` gives separate send/receive halves that can be used concurrently.

### Bytearray Reuse Pattern

The Python code uses a global reusable bytearray to avoid allocation. In Rust, the equivalent is a pool or a dedicated buffer per WebSocket connection:

```rust
struct PayloadEncoder {
    buffer: Vec<u8>,
}

impl PayloadEncoder {
    fn encode(&mut self, payload: &MultiFramePayload, display_sizes: Option<&DisplaySizes>) -> &[u8] {
        self.buffer.clear();
        // Write header + per-camera headers + JPEG data + footer
        // self.buffer grows automatically if needed (Vec)
        &self.buffer
    }
}
```

`Vec<u8>` already reuses its allocation on `clear()` — no global mutable state needed.

---

## Functionality Preserved

1. **Exact binary protocol** — bit-identical PayloadHeader (24 bytes) + FrameHeader (56 bytes) layout matching Python numpy dtypes
2. **Recorder sees every frame** — unbounded channel from dispatcher to recording thread, never drops
3. **WebSocket sees latest only** — shared slot updated each multiframe; WebSocket polls and skips already-seen frame numbers
4. **Framerate tracking** — `FramerateTracker` computes server + display FPS independently, sent at ~4 Hz
5. **Multi-frame assembly** — gatherer validates all cameras at same frame number (panics on desync)
6. **Multiple camera groups** — each group has its own gatherer + dispatcher threads
7. **Log relay** — `tracing` → `broadcast::channel` → `mpsc` bridge → WebSocket text messages

## Functionality Changed (by design)

- **No JPEG re-encode** — MJPEG passes through; only lossless rotation applied
- **No resize to 50%** — native resolution sent to frontend
- **No `frameNumber` backpressure** — TCP backpressure is the only flow control
- **No state updates every 1s** — not implemented
- **No ping/pong** — WebSocket keep-alive not yet needed
- **Multiframe timestamp** — uses mean of `frame_available_ns` across cameras, not grab midpoint
