# Component #3: CameraOrchestrator + Sync Gate + Capture Loop

Status: **ANALYZED — stable reference artifact**

Files analyzed:
- `skellycam/core/camera_group/camera_orchestrator.py` — CameraOrchestrator, sync gate, recording boundaries
- `skellycam/core/camera_group/camera_status.py` — CameraStatus (11 boolean flags + frame_count)
- `skellycam/core/camera/opencv/opencv_camera_worker_method.py` — camera worker entry point
- `skellycam/core/camera/opencv/opencv_camera_loop.py` — main capture loop
- `skellycam/core/camera/opencv/opencv_helpers/setup_opencv_camera_loop.py` — two-phase setup
- `skellycam/core/camera/opencv/opencv_helpers/opencv_get_frame.py` — grab/retrieve with timestamps
- `skellycam/core/camera/opencv/opencv_helpers/camera_loop_update_checks.py` — per-iteration checks
- `skellycam/core/camera/opencv/opencv_helpers/handle_recording_updates.py` — recording info + finish
- `skellycam/core/camera/opencv/opencv_helpers/handle_video_recording_loop.py` — record frame dispatch

Docs analyzed:
- `skellycam-docs/docs/core/frame-perfect-sync.mdx`
- `skellycam-docs/docs/technical/frame-synchronization.mdx`

---

## What It Does

This is the **hot loop** — the time-critical core that must be protected from everything else. Three sub-components work together:

### CameraOrchestrator

Manages synchronized frame capture across all cameras in a group. Three responsibilities:

**1. Synchronization gate** (`should_grab_by_id`):

```python
def should_grab_by_id(self, camera_id) -> bool:
    if not self.all_ready:  # any camera not connected/paused/closing/updating/error?
        return False
    return self._all_camera_counts_greater_than_or_equal_to_camera(camera_id)

def _all_camera_counts_greater_than_or_equal_to_camera(self, camera_id):
    counts = deepcopy(self.camera_frame_counts)  # snapshot all counts from shared memory
    return all(counts[camera_id] <= count for count in counts.values())
```

Rule: a camera may only grab when its frame count ≤ all other cameras. This ensures no camera gets more than 1 frame ahead. All cameras poll concurrently; when all reach the same count, they all pass the gate at roughly the same instant.

**2. Recording boundaries** (`should_record_frame_number`):

```python
def should_record_frame_number(self, frame_number: int) -> tuple[bool, bool]:
    should_record = (first_recording_frame_number != -1 
                     and frame_number >= first_recording_frame_number)
    if last_recording_frame_number != -1:
        should_record = frame_number < last_recording_frame_number
        should_finish = frame_number >= last_recording_frame_number
    return should_record, should_finish
```

Boundary values are set by CameraGroup while all cameras are paused (guaranteeing atomic setup). The +3 frame offset on start/stop ensures all cameras see the same boundary.

**3. Global status queries**: `all_ready`, `all_cameras_recording`, `all_cameras_paused`, `any_cameras_paused`, `any_cameras_alive`, `camera_frame_counts`, `pause()`, `unpause()`, `close()`

### CameraStatus

Per-camera flags stored as `multiprocessing.Value` for cross-process visibility:

| Flag | Type | Purpose |
|------|------|---------|
| `connected` | `Value("b")` | Camera hardware initialized |
| `grabbing_frame` | `Value("b")` | Inside grab/retrieve cycle (gates recording flag reads) |
| `recording_in_progress` | `Value("b")` | VideoRecorder active |
| `is_recording_frame` | `Value("b")` | Currently writing frame to disk |
| `is_paused` | `Value("b")` | Paused (not grabbing) |
| `should_pause` | `Value("b")` | Pause command received |
| `should_close` | `Value("b")` | Close command received |
| `closing` | `Value("b")` | In closing sequence |
| `closed` | `Value("b")` | Fully closed |
| `updating` | `Value("b")` | Config update in progress |
| `error` | `Value("b")` | Error state |
| `frame_count` | `Value("q")` | Last frame number grabbed (signed 64-bit) |

The `ready` property: `connected AND NOT (should_pause OR should_close OR closing OR closed OR updating OR error)`

`signal_error()` atomically disables `connected` and enables `error`. `signal_closing()` clears all active flags.

### Camera Capture Loop

The per-camera loop runs in its own process. Exact execution order per iteration:

```
1. camera_loop_update_checks()     ← check PubSub for recording info, config changes, pause
2. if should_close: break          ← exit gate
3. if is_paused: wait_1ms; continue ← spin-wait at 1ms
4. if not should_grab_by_id():     ← SYNC GATE
      wait_10us; continue          ← spin-wait at 10μs
5. grabbing_frame = True           ← begin critical section
6. opencv_get_frame():             ← GRAB + RETRIEVE
      pre_grab_ns = now()
      cap.grab()
      post_grab_ns = now()
      pre_retrieve_ns = now()
      cap.retrieve(image=pre_allocated)  ← decode MJPEG→BGR into pre-allocated numpy array
      post_retrieve_ns = now()
      frame_number += 1
      draw frame stamp text on image
   (retry up to 30 times on failure; if camera closed, raise RuntimeError)
7. should_record_frame, should_finish = orchestrator.should_record_frame_number(frame_number)
   ← CRITICAL: read BEFORE clearing grabbing_frame
8. grabbing_frame = False          ← end critical section
9. camera_shm.put_frame(frame, overwrite=True)  ← write to shared memory ring buffer
10. handle_video_recording(should_record, should_finish)  ← record to cv2.VideoWriter
11. check_framerate_reset()        ← if frames too slow for 30+ iterations, re-create cv2.VideoCapture
12. initialize_frame_recarray()    ← clear timestamps for next iteration
13. frame_count.value = frame_number  ← increment shared frame count (ungates other cameras)
```

**Initialization barrier** (in `setup_opencv_camera_loop`, before loop starts):
1. Connect to camera → publish extracted config
2. Wait for shared memory DTO from main process → recreate SHM
3. Set `connected = True`
4. Wait for `orchestrator.all_ready` (all cameras initialized)
5. While waiting: burn dummy frames with `cv2.read()` to clear hardware buffer
6. Create initial frame recarray with `frame_number = -1`

---

## Python-Specific Problems This Architecture Solves

| Problem | Python Solution | Why It Exists |
|---------|----------------|---------------|
| No shared memory between processes | `multiprocessing.Value("q")` for frame_count, `multiprocessing.Value("b")` for status flags | Each process has its own address space |
| No atomic snapshot of distributed state | `deepcopy(self.camera_frame_counts)` in sync gate — copies all values from shared memory into a local dict, then checks | Must read all cameras' counts consistently; `deepcopy` over a dict comprehension gives a point-in-time snapshot |
| Need to coordinate N independent processes | Frame-count-gated protocol — each camera polls `should_grab_by_id()`, only proceeds when its count ≤ all others | No centralized barrier primitive across processes; polling with a shared-memory predicate is the most efficient available |
| Grab/retrieve split for minimal inter-camera timing spread | Two OpenCV calls with timestamps before/after each. Pre-allocated numpy array for `retrieve(image=)` to avoid allocation in hot loop | Minimize time between cameras' grab calls; avoid malloc in the hot path |
| Recording flag race conditions | Read recording flags AFTER grab but BEFORE clearing `grabbing_frame` | If recording boundaries changed between reading flags and grabbing, cameras could disagree on whether to record frame N |
| Camera "drift" detection | `check_framerate_reset()` — if 30+ consecutive frames exceed 2× target duration, release and re-create the cv2.VideoCapture | USB cameras can enter a degraded state; resetting the capture object recovers |
| Error in one camera must shut down all | `signal_error()` → `ipc.kill_everything()` sets global kill flag | One camera failing means the synchronized group is broken; clean shutdown preserves data |
| Ensure recording finalization even on crash | `finally` block in loop: if `video_recorder` exists, call `finish_recording()` | Must flush video file and timestamps even if the loop crashes |
| All cameras must start at frame 0 together | Initialization barrier — all cameras wait for `all_ready` before entering the main loop. Dummy frames burned to clear stale buffers | Without synchronization, cameras would start at different frame numbers |

---

## What Changes in Rust

| Python Concept | Rust Equivalent | Key Difference |
|---------------|----------------|---------------|
| `multiprocessing.Value("q")` for frame_count | `Arc<AtomicI64>` or `Arc<AtomicU64>` per camera | Same atomic semantics, no special constructor |
| 11 `multiprocessing.Value("b")` per camera | `Arc<AtomicBool>` per flag OR `Arc<AtomicU16>` bitfield OR `Arc<Mutex<CameraState>>` | Can choose representation based on access pattern. Bitfield gives atomic read of all flags at once. |
| `deepcopy(self.camera_frame_counts)` in sync gate | Read `AtomicI64` values into local array; compare. `Ordering::Acquire` for consistency. | No `deepcopy` needed — `AtomicI64::load()` returns a copy |
| `should_grab_by_id()` polling with `wait_10us()` | Same polling pattern OR blocking `sync_channel(1)` per camera (structural backpressure) | **Key design decision**: polling vs. blocking. Blocking gives lockstep without spin-wait but changes the control flow. See below. |
| `cap.grab()` + `cap.retrieve()` | `camera.frame()` (nokhwa combines them) OR split into raw buffer + decode | nokhwa supports both; the split is available via `CameraBuffer` + `.decode_image::<RgbFormat>()` |
| Pre-allocated numpy recarray for `retrieve(image=)` | Pre-allocated `Vec<u8>` passed by `&mut [u8]`. nokhwa's `decode_image_to_buffer()` can write into existing buffer. | Same zero-allocation pattern. `Vec<u8>` is the heap buffer. |
| `while not frame_success` retry loop (max 30) | Same retry loop. Rust's `Result` makes the error path explicit. | `match camera.frame() { Ok(buf) => ..., Err(e) => { fail_count += 1; continue; } }` |
| `finally` block for recording finalization | `Drop` impl on a `CameraLoopGuard` struct that holds the VideoRecorder handle | Deterministic cleanup — compiler guarantees `Drop` runs |
| PubSub for recording info / config changes | `mpsc::Receiver` per camera for commands, or `tokio::sync::broadcast` for multi-consumer | Typed channels replace untyped PubSub queues |
| `framerate` median calculation from deque | Same: `VecDeque<f64>` with `OrderedFloat` for `f64::total_cmp` | Rust's `sort_by` + index or the `order-stat` crate for O(n) median |
| `check_framerate_reset()` re-creates cv2.VideoCapture | nokhwa `Camera::new()` — recreate entire camera handle | Same recovery pattern. nokhwa camera handles are not `Clone` or `Copy` — must drop and re-create. |
| `initialize_frame_recarray()` clears timestamps | `FramePacket` is owned, constructed fresh each iteration. No clear needed. | Ownership means each frame is a new allocation (or pool-allocated). No overwrite-in-place pattern. |
| OpenCV BGR → JPEG for frontend | `image` crate for rotation + `image::codecs::jpeg` for encoding | RGB order (not BGR). Same JPEG quality parameter. |
| Drawing frame stamp on image | `imageproc` crate or manual pixel writes | Can use `imageproc::drawing::draw_text` or a simpler bitmap font (like the existing test project's 5x7 font) |

---

## The Central Design Decision: Polling Gate vs. Structural Backpressure

The Python sync gate uses **polling**: each camera calls `should_grab_by_id()` in a `while` loop, spinning at 10μs. This is necessary because Python processes can't block each other — `multiprocessing.Value` has no "wait for value" primitive.

Rust offers two approaches:

### Option A: Polling (faithful port)

```rust
// Camera thread loop
loop {
    if !orchestrator.should_grab_by_id(camera_id) {
        spin_sleep::sleep(Duration::from_micros(10));
        continue;
    }
    // grab + process + record...
    frame_count.store(frame_number, Ordering::Release);
}
```

- Same polling behavior, 10μs spin
- `should_grab_by_id` reads `AtomicI64` values from all cameras
- No structural change to the sync mechanism
- Familiar, proven correctness

### Option B: Structural backpressure (Rust-native)

```rust
// Each camera thread has sync_channel(1) to the gatherer
// Gatherer runs:
loop {
    let f0 = cam0_rx.recv();  // blocks until camera 0 sends
    let f1 = cam1_rx.recv();  // blocks until camera 1 sends
    // -- all cameras have sent frame N --
    let payload = MultiFramePayload { frames: [f0, f1], step: n };
    broadcast_tx.send(payload);
    n += 1;
    // Cameras unblock, proceed to frame N+1
}
```

- Cameras `send()` their frame to the gatherer, then block on the next `send()` (sync_channel capacity 1)
- Gatherer's `recv()` from all cameras is an implicit barrier
- No polling, no spin-wait, no atomics for the gate
- **Consequence**: cameras CAN'T run independently — they're structurally gated by the gatherer
- **Concern from SkellyCam docs**: "if one camera lags, the others must wait" — this is the DESIRED behavior (lockstep)

### Decision: Option B + Grab/Decode Split (CONFIRMED)

**Structural backpressure** eliminates the spin-wait entirely. It's also simpler — no `should_grab_by_id()` logic, no atomics for frame counts. The gatherer's `recv()` calls ARE the synchronization.

**Grab/decode split across threads**: the camera thread does ONLY the raw grab (thin, fast). Decode happens in a separate decoder thread. This reduces inter-camera grab timing spread.

#### Pipeline topology (per camera)

```
CAMERA THREAD (grab only)         DECODER THREAD              GATHERER
camera.frame() → CameraBuffer     raw_rx.recv()
  (raw MJPEG/YUY2 from USB)        ↓
timestamp = Instant::now()        buffer.decode_image()
  ↓                                 (MJPEG→RGB, expensive)
raw_tx.send(RawFrame {                ↓
  buffer, ts, camera_id            decoded_tx.send(
})  ← BLOCKED if decoder             FramePacket {            decoder_rx.recv() ← BLOCKS
     hasn't consumed prev               image, ts,             until decoder sends
     frame (sync_channel(1))            camera_id              ↓
                                    })                   f0 = decoder0_rx.recv()
                                                          f1 = decoder1_rx.recv()
                                                    BACKPRESSURE FLOW:
                                                    gatherer blocks decoders,
                                                    decoders block camera threads
                                                    All at step N → gatherer emits
                                                    → decoders unblock → cameras unblock
```

**What CameraStatus flags become**: With structural backpressure, many flags are unnecessary:
- `grabbing_frame` — gone (backpressure is the gate)
- `frame_count` — gone (gatherer tracks step numbers)
- `is_recording_frame` — moves to recorder thread
- `connected`, `is_paused`, `should_pause`, `should_close`, `closing`, `closed`, `updating`, `error` — still needed for lifecycle
- `recording_in_progress` — still needed for recording coordination

---

## Functionality That Must Be Preserved

1. **Frame-count-gated lockstep** — now structural via sync_channel(1) + gatherer recv, not polling
2. **Grab separate from decode across threads** — camera thread grabs raw buffer; decoder thread decodes; timestamps at both stages
3. **Pre-allocated frame buffers** — decoder writes into pre-allocated `Vec<u8>`, no allocation in hot path
4. **Recording boundaries via pause + frame offset** — same pattern, but recording happens in a recorder thread fed by broadcast
5. **Pause gate** — paused camera threads skip grab; paused decoders skip decode
6. **Initialization barrier** — all cameras open, publish config, then gatherer starts first recv cycle
7. **Recording boundary coordination** — `first/last_recording_frame_number` set while paused, with +3 frame offset
8. **Per-frame timestamps** — grab timestamps on camera thread, retrieve timestamps on decoder thread
9. **Camera error → group shutdown** — error in any thread triggers clean shutdown; channels break, Drop impls fire
10. **Recording finalization on crash** — video files closed and timestamps flushed via Drop impls
11. **Framerate tracking** — rolling median on camera thread (grab-to-grab duration)
12. **Frame stamp on image** — drawn on decoder thread after decode
