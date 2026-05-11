# Component #5: Recording Pipeline

Status: **ANALYZED — stable reference artifact**

Files analyzed:
- `skellycam/core/recorders/videos/video_recorder.py` — VideoRecorder (per-camera, OpenCV VideoWriter)
- `skellycam/core/recorders/recording_finalizer.py` — RecordingFinalizer (validation, timestamp processing)
- `skellycam/core/recorders/videos/recording_info.py` — RecordingInfo (paths, UUIDs, folder schema)
- `skellycam/core/camera_group/camera_orchestrator.py` — recording boundary coordination (pause/unpause, frame numbers)
- `skellycam/core/camera/opencv/opencv_helpers/handle_recording_updates.py` — PubSub-driven recorder lifecycle
- `skellycam/core/camera/opencv/opencv_helpers/handle_video_recording_loop.py` — per-frame recording logic
- `skellycam/core/camera_group/camera_group.py` — start_recording(), stop_recording(), finalize_recording()
- `skellycam/core/timestamps/numpy_timestamps/process_and_save_recording_timestamps.py` — timestamp computation pipeline
- `skellycam/core/timestamps/numpy_timestamps/process_recording_timestamps.py` — durations from timestamps
- `skellycam/core/timestamps/numpy_timestamps/calculate_timestamps_numpy.py` — numpy-based duration/statistics math
- `skellycam/core/timestamps/recording_timestamp_stats.py` — RecordingTimestampsStats dataclass
- `skellycam/core/timestamps/full_timestamp.py` — FullTimestamp (UTC + local + perf_counter mapping)
- `skellycam/core/types/numpy_record_dtypes.py` — all timestamp/duration/stats dtype definitions
- `skellycam/core/types/frame_dtype_factories.py` — creates per-camera frame dtype from config
- `skellycam-rust/rust_webcam_app/src/recorder.rs` — existing Rust ffmpeg subprocess recorder

---

## How It Works (Python)

### Layer 1: VideoRecorder (per-camera encoder)

`VideoRecorder` wraps OpenCV's `cv2.VideoWriter`. Each camera gets its own instance, created from a `RecordingInfoMessage` received via PubSub.

**Creation** (`VideoRecorder.create()`):
1. Determine video image shape — depends on rotation (rotated 90°/270° swaps width/height)
2. Resolve a working fourcc codec for this platform (falls back from requested)
3. Build output path: `{videos_folder}/{recording_name}.camera{camera_id}.{ext}`
4. Create `cv2.VideoWriter` with the resolved codec, framerate, and shape
5. Validate writer opened successfully

**Per-frame** (`record_frame()`):
1. Validate frame number is consecutive (previous + 1)
2. Optionally rotate image via `cv2.rotate()`
3. Validate image shape matches expected
4. Timestamp: `pre_frame_record_ns = time.perf_counter_ns()`
5. Write frame to VideoWriter: `self.video_writer.write(image)`
6. Timestamp: `post_frame_record_ns = time.perf_counter_ns()`
7. Validate writer still open
8. Append frame_metadata copy to `self.video_frame_metadata` list

**Finish** (`finish_and_close()`):
1. Release VideoWriter
2. Return accumulated `video_frame_metadata` list (for RecordingFinalizer)

**What happens to metadata**: The camera loop calls `finish_recording()` which publishes a `RecordingFinishedMessage` to the PubSub. This message carries the `RecordingInfo` object and the `frame_metadatas` list. The main process collects these from all cameras before running the RecordingFinalizer.

### Layer 2: Recording Boundary Coordination (CameraOrchestrator)

The orchestrator holds two shared `multiprocessing.Value("q")` (signed 64-bit int):

```
first_recording_frame_number: Synchronized  // -1 when not recording
last_recording_frame_number: Synchronized   // -1 when recording has no end
```

`should_record_frame_number(frame_number)` returns `(should_record: bool, should_finish: bool)`:
- If `first != -1` AND `frame_number >= first` AND `frame_number < last` → record
- If `frame_number >= last` → finish (don't record this frame)
- If `last == -1` AND `frame_number >= first` → record (recording in progress, no end set yet)

The `recording_in_progress` flag on each CameraStatus is set to True when the VideoRecorder is created, used by `all_cameras_recording` to determine when everyone is ready.

**The pause-before-record protocol** (in `CameraGroup.start_recording()`):

```
1. pause all cameras (await all is_paused == True)
2. frame_count = max(current frame counts across all cameras)
3. first_recording_frame_number = frame_count + 3   ← +3 offset ensures boundary visibility
4. last_recording_frame_number = -1                 ← no end yet
5. publish RecordingInfoMessage to PubSub           ← each camera creates VideoRecorder
6. wait 10ms
7. unpause all cameras                              ← recording begins
```

**The pause-before-stop protocol** (in `CameraGroup.stop_recording()`):

```
1. pause all cameras
2. stop audio recorder (if active)
3. frame_count = max(current frame counts)
4. first_recording_frame_number = -1                ← clear start
5. last_recording_frame_number = frame_count + 3
6. unpause all cameras
7. wait for RecordingFinishedMessage from every camera via PubSub
8. create RecordingFinalizer, run finalize_recording()
```

The `+3` offset: cameras are paused at slightly different points in their loops (one camera might be at frame 47 while another is at frame 49). The +3 ensures every camera sees the boundary after they've had 3 frames of running post-unpause to synchronize their recording start. Any frames between unpause and the boundary are still captured but not recorded.

### Layer 3: Recording Lifecycle in the Camera Loop

In the camera hot loop, after grabbing/retrieving a frame and writing to SHM:

1. `check_for_new_recording_info(...)` — polls PubSub subscription for new `RecordingInfoMessage`
   - If received: close old recorder (if exists), create new `VideoRecorder`, set `recording_in_progress = True`
   - Wait-spin until `orchestrator.all_cameras_recording` is True
2. `handle_video_recording(...)` — called every frame
   - `should_record_frame, should_finish = orchestrator.should_record_frame_number(frame_number)`
   - If `should_record_frame`: set `is_recording_frame = True`, call `video_recorder.record_frame(frame)`, set `is_recording_frame = False`
   - If `should_finish` AND `video_recorder is not None`: call `finish_recording()` which publishes `RecordingFinishedMessage` to PubSub

### Layer 4: RecordingFinalizer

After all cameras finish recording and publish their `RecordingFinishedMessage`s:

```
finalize_recording():
  1. Collect RecordingFinishedMessages from all cameras (via PubSub polling)
  2. Validate all messages have same RecordingInfo
  3. Create RecordingFinalizer with: recording_info, camera_configs, frame_metadatas_by_camera
  4. Save RecordingInfo JSON (with camera configs embedded)
  5. Process timestamps → per-camera CSVs, multiframe CSV, statistics
  6. Write README in videos folder
  7. Validate: video files exist, same frame count, timestamps match
  8. Return (recording_info, timestamp_stats)
```

**Validation checks:**
1. All video files exist on disk and are non-empty
2. All videos have same frame count
3. Timestamp files exist for all cameras
4. Timestamp row count matches video frame count for each camera

### Layer 5: Timestamp Pipeline

The timestamp lifecycle, from hot path to final statistics:

**Frame metadata dtype** (one per frame per camera):
```python
FRAME_METADATA_DTYPE = [
    ('camera_info', FRAME_CAMERA_INFO_DTYPE),     # camera_id, camera_index, rotation, color_channels
    ('frame_number', np.int64),                   # absolute frame number
    ('timebase_mapping', TIMEBASE_MAPPING_DTYPE), # utc_time_ns, perf_counter_ns, local_time_utc_offset
    ('timestamps', FRAME_LIFECYCLE_TIMESTAMPS_DTYPE),
]
```

**Raw timestamp fields** (8 stages, all i64 nanoseconds):
```
initialized_ns           ← set once at camera startup
pre_frame_grab_ns        ← right before cv2.VideoCapture.grab()
post_frame_grab_ns       ← right after grab returns
pre_frame_retrieve_ns    ← right before cv2.VideoCapture.retrieve()
post_frame_retrieve_ns   ← right after retrieve returns
pre_copy_to_camera_shm_ns ← right before numpy copy to shared memory
post_copy_to_camera_shm_ns ← right after SHM write
pre_frame_record_ns      ← right before cv2.VideoWriter.write()
post_frame_record_ns     ← right after write returns
```

**Duration computation** (from timestamp pairs):
```
idle_before_frame_grab_ns    = pre_frame_grab - initialized_ns
during_frame_grab_ns         = post_frame_grab - pre_frame_grab
idle_before_retrieve_ns      = pre_frame_retrieve - post_frame_grab
during_frame_retrieve_ns     = post_frame_retrieve - pre_frame_retrieve
idle_before_copy_to_shm_ns   = pre_copy_to_shm - post_frame_retrieve
during_copy_to_shm_ns        = post_copy_to_shm - pre_copy_to_shm
idle_before_frame_record_ns  = pre_frame_record - post_copy_to_shm
during_frame_record_ns       = post_frame_record - pre_frame_record
total_frame_processing_time  = sum(all "during_X" + all "idle_before_X" except idle_before_grab)
total_camera_idle_time       = idle_before_frame_grab  (minimally; "someday" more)
```

**Processing pipeline**:
```
frame_metadatas_by_camera (dict[camera_id → list of recarrays])
  → validate_frame_metadatas() → frame_numbers, timebase_mapping
  → process_recording_timestamps() → all_timestamps array (num_cameras × num_frames)
      → calculate_durations() → all_durations array
  → create_and_save_camera_csvs() → per-camera timestamp CSV files
  → create_and_save_multiframe_csv() → multiframe CSV (with cross-camera sync stats)
  → save_timestamp_statistics_summary() → RecordingTimestampsStats
```

**CSV output files**:
- Per-camera: `{timestamps_folder}/{recording_name}.camera{camera_id}.timestamps.csv`
- Multiframe: `{timestamps_folder}/{recording_name}_timestamps.csv`
- Stats text: `{timestamps_folder}/{recording_name}_stats.txt`
- Stats JSON: `{timestamps_folder}/{recording_name}_stats.json`

**Recording folder layout**:
```
{recording_directory}/{recording_name}/
  {recording_name}_info.json
  synchronized_videos/
    {recording_name}.camera{camera_id}.mp4  (per camera)
    {recording_name}.audio.wav              (optional)
    synchronized_videos_README.md
  timestamps/
    {recording_name}.camera{camera_id}.timestamps.csv
    {recording_name}_timestamps.csv
    {recording_name}_stats.txt
    {recording_name}_stats.json
```

---

## Python-Specific Problems This Architecture Solves

| Problem | Python Solution | Why It Exists |
|---------|----------------|---------------|
| Cross-process encoder access | Per-camera VideoRecorder inside camera process — writes directly, collects metadata locally | OpenCV VideoWriter must be created in the same process as the camera (GIL/context) |
| Platform-specific codec selection | `resolve_writer_fourcc()` tries requested codec, falls back to platform-appropriate one | OpenCV's codec availability varies wildly by platform/build |
| Metadata must cross process boundary | Camera process publishes `RecordingFinishedMessage` with serialized metadata list via PubSub | Main process needs metadata for finalization, but camera process owns it |
| Recording boundary visibility | `first/last_recording_frame_number` are shared `multiprocessing.Value` writable by main, readable by children | Must coordinate start/stop across process boundaries |
| Structured timestamp storage | numpy structured dtype — fixed schema, aligned memory layout, vectorized math | NumPy is Python's only performant multi-dimensional array option |
| Async event loop blocking | `await await_1ms()` every 1000 frames during duration computation | Prevents the asyncio event loop from starving during long CPU operations |
| Duration math | Manual double-loop over (num_cameras, num_frames) with per-element field access | NumPy recarray vectorization is limited for cross-field operations |
| Cross-camera validation | Multi-step validation with early returns and specific error messages | Debugging multi-process recording is hard; verbose errors help |
| Timestamp extensibility | Fixed numpy dtype — adding a stage requires changing dtype definition + all downstream code | Python has no `#[non_exhaustive]` or sealed trait equivalent for struct fields |

---

## Existing Rust Code (webcam test project)

The `rust_webcam_app/src/recorder.rs` already has a working ffmpeg subprocess recorder:

```rust
pub struct VideoRecorder {
    child: Child,
    stdin: Option<ChildStdin>,
    frame_count: u64,
}
```

- `start(width, height, fps, output_path)` — spawns ffmpeg with `-f rawvideo -pixel_format rgb24` reading from `pipe:0`
- `feed_frame(rgb_data: &[u8])` — writes raw RGB24 bytes to stdin
- `finish(mut self)` — drops stdin (sends EOF), waits for ffmpeg to exit, checks status
- `Drop` impl — kills ffmpeg if `finish()` was never called

This is the foundation for the per-camera recorder in the SkellyCam port. It needs to be extended with:
- Frame metadata collection (timestamps, frame numbers)
- Recording boundary awareness (start/stop commands)
- `finish()` returning metadata rather than just status
- Configurable codec parameters from CameraConfig

---

## What Changes in Rust

### VideoRecorder: ffmpeg replaces OpenCV VideoWriter

The Python code uses OpenCV's `cv2.VideoWriter` because it's already a dependency (camera capture). In Rust, we use ffmpeg subprocess (avoiding the opencv crate entirely):

- **Pro**: No OpenCV dependency. ffmpeg has better codec support, more predictable cross-platform behavior.
- **Con**: Requires ffmpeg on PATH. Same constraint as the webcam test project.
- **Open question**: Should we support a non-ffmpeg fallback (e.g., mp4 crate for pure-Rust encoding)?

The recorder must additionally:
- Collect per-frame timestamps (`pre_frame_record_ns`, `post_frame_record_ns`)
- Track frame metadata (camera_info, frame_number, timebase_mapping)
- Return accumulated metadata on finish

```rust
pub struct VideoRecorder {
    child: Child,
    stdin: Option<ChildStdin>,
    frame_count: u64,
    // NEW: metadata collection
    frame_metadatas: Vec<FrameMetadata>,
    camera_id: String,
    camera_index: i32,
    timebase_mapping: TimebaseMapping,
}

impl VideoRecorder {
    pub fn feed_frame(&mut self, rgb_data: &[u8], frame_number: i64) -> Result<()> {
        let pre_ns = perf_counter_ns();
        self.stdin.as_mut().unwrap().write_all(rgb_data)?;
        let post_ns = perf_counter_ns();
        
        self.frame_metadatas.push(FrameMetadata {
            camera_info: CameraInfo { ... },
            frame_number,
            timebase_mapping: self.timebase_mapping,
            timestamps: FrameTimestamps {
                pre_frame_record_ns: pre_ns,
                post_frame_record_ns: post_ns,
            },
        });
        self.frame_count += 1;
        Ok(())
    }

    pub fn finish(mut self) -> Result<Vec<FrameMetadata>> {
        drop(self.stdin.take());
        let status = self.child.wait()?;
        if !status.success() { bail!(...); }
        Ok(self.frame_metadatas)
    }
}
```

### Recording Boundaries: Channels replace shared multiprocessing.Values

In Python, `first_recording_frame_number` and `last_recording_frame_number` are `multiprocessing.Value("q")` because the main process writes them and camera processes read them. In Rust, these are just fields on the orchestrator, since everything runs in one process:

```rust
// CameraOrchestrator in Rust
pub struct CameraOrchestrator {
    camera_statuses: HashMap<CameraId, CameraStatus>,
    first_recording_frame_number: AtomicI64,  // -1 = not recording
    last_recording_frame_number: AtomicI64,   // -1 = no end yet
}
```

The pause-before-record protocol is identical. The `+3` offset is preserved.

### PubSub replaced by direct channels

- `RecordingInfoMessage` → sent via a channel from CameraGroup to each camera thread's control loop
- `RecordingFinishedMessage` → sent via a channel from each camera's recorder back to CameraGroup

No PubSub infrastructure needed. Just `mpsc::channel` or `tokio::sync::mpsc`.

### RecordingFinalizer: sync Rust, no async needed

The Python finalizer uses `await` because timestamp processing happens on the asyncio event loop and must yield to avoid blocking. In Rust:

- Run finalization on a dedicated thread via `tokio::task::spawn_blocking()`
- Or make it fully synchronous (the API handler calling `stop_recording` can await the blocking task)
- Duration computation uses iterators, rayon, or plain loops — all faster than numpy double-loops

### Timestamp System: Extensibility Design

**The problem**: Python's timestamp schema is fixed. `FRAME_LIFECYCLE_TIMESTAMPS_DTYPE` has exactly 8 named fields. Adding a new pipeline stage (e.g., "pre_rt_tracker" / "post_rt_tracker") requires:
1. Adding fields to the dtype
2. Adding durations to the duration dtype
3. Adding columns to both CSV dtypes
4. Adding fields to `RecordingTimestampsStats`
5. Updating all code that references specific field names

This is brittle and makes the timestamp system hard to reuse in other contexts.

**The Rust approach**: Define timestamp stages as an extensible, ordered collection rather than a fixed struct.

```rust
/// A timestamp stage in the frame lifecycle.
/// New stages can be added without breaking existing code.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum TimestampStage {
    // --- Core camera stages ---
    PreFrameGrab,
    PostFrameGrab,
    PreFrameRetrieve,
    PostFrameRetrieve,
    PreCopyToCameraShm,
    PostCopyToCameraShm,
    PreFrameRecord,
    PostFrameRecord,

    // --- Future stages (not yet used, designed for later) ---
    // PreRtPipeline,
    // PostRtPipeline,
    // PreMediapipeTracker,
    // PostMediapipeTracker,
}

/// Ordered timestamp entries for a single frame.
#[derive(Debug, Clone)]
pub struct FrameTimestamps {
    /// Ordered map of stage → nanoseconds (perf_counter).
    /// BTreeMap guarantees iteration order for CSV output.
    stamps: BTreeMap<TimestampStage, i64>,
}

impl FrameTimestamps {
    /// Record a timestamp for a stage.
    pub fn record(&mut self, stage: TimestampStage, ns: i64) {
        self.stamps.insert(stage, ns);
    }

    /// Duration between post and pre of a stage.
    pub fn duration(&self, pre: TimestampStage, post: TimestampStage) -> Option<i64> {
        let pre_ns = self.stamps.get(&pre)?;
        let post_ns = self.stamps.get(&post)?;
        Some(post_ns - pre_ns)
    }

    /// Idle time between post of previous stage and pre of current.
    pub fn idle_before(&self, stage: TimestampStage, prev_stage: TimestampStage) -> Option<i64> {
        let prev_post = self.stamps.get(&prev_stage)?;
        let this_pre = self.stamps.get(&stage)?;
        Some(this_pre - prev_post)
    }

    /// All stage names present, in order.
    pub fn stages(&self) -> impl Iterator<Item = TimestampStage> + '_ {
        self.stamps.keys().copied()
    }
}
```

**Duration computation becomes generic**: Instead of hardcoding `during_frame_grab_ns = post - pre` for each stage, we iterate over all stages and compute durations generically:

```rust
impl FrameTimestamps {
    /// Compute all durations between paired (pre_X, post_X) stages.
    pub fn compute_durations(&self) -> BTreeMap<String, i64> {
        let mut durations = BTreeMap::new();
        let stages: Vec<_> = self.stamps.keys().copied().collect();

        for window in stages.windows(2) {
            let (a, b) = (window[0], window[1]);
            let a_ns = self.stamps[&a];
            let b_ns = self.stamps[&b];

            if is_pre_post_pair(a, b) {
                // "during_X_ns"
                durations.insert(format!("during_{}", stage_base_name(b)), b_ns - a_ns);
            } else {
                // "idle_before_X_ns"
                durations.insert(format!("idle_before_{}", stage_base_name(b)), b_ns - a_ns);
            }
        }

        durations
    }
}
```

**CSV output driven by the enum**: Use `strum` or manual `Display` impl to iterate over all enum variants and produce CSV columns dynamically. Adding a new stage = adding enum variants + `Display` arms. Everything downstream (duration computation, CSV writing, statistics) picks it up automatically.

**Statistics**: Instead of 24+ named fields in `RecordingTimestampsStats`, use a map:

```rust
pub struct RecordingTimestampsStats {
    recording_name: String,
    num_cameras: usize,
    num_frames: usize,
    total_duration_sec: f64,

    /// Per-stage statistics, keyed by stage base name.
    stage_stats: BTreeMap<String, StageStatistics>,
}

pub struct StageStatistics {
    median_ms: f64,
    mean_ms: f64,
    std_ms: f64,
    min_ms: f64,
    max_ms: f64,
    pct_of_total: f64,
}
```

This means adding a new stage automatically produces statistics for it — no new fields needed.

**The "copy to SHM" stage is a no-op for in-process Rust**: With threads sharing address space, there's no copy to shared memory. The `PreCopyToCameraShm` / `PostCopyToCameraShm` stages can be either:
- Removed (they bracket a zero-duration no-op)
- Kept as always-equal timestamps for CSV compatibility

Decision needed: preserve CSV compatibility (keep the column, always ~0ns) or drop the column.

### The "recording in progress" safety net

Python: `Drop` impl on Rust's VideoRecorder handles cleanup if `finish()` is never called (kill ffmpeg, close stdin). Python uses try/finally or context managers. Rust's deterministic Drop is strictly better here — no zombie ffmpeg processes even on panic.

---

## Functionality That Must Be Preserved

1. **Per-camera video files** — one mp4 per camera, named `{recording_name}.camera{camera_id}.mp4`
2. **Pause-before-record protocol** — all cameras paused, boundaries set, then unpaused
3. **+3 frame offset** — `first_recording_frame_number = max(current_frames) + 3`
4. **Consecutive frame validation** — recorder checks each frame number is prev + 1
5. **Image rotation before encode** — same rotation logic as camera loop
6. **Per-frame timestamps** — pre/post recording timestamps for each frame
7. **Frame metadata collection** — accumulated during recording, returned on finish
8. **RecordingInfo JSON** — saved with camera configs, UUID, timestamps
9. **Per-camera timestamp CSV** — all 8 timestamp fields + durations per frame
10. **Multiframe timestamp CSV** — cross-camera sync stats per frame
11. **Statistics** — median/mean/std/min/max for each stage, framerate, sync
12. **Validation** — video files exist, same frame count, timestamps match videos
13. **Recording stops on camera error** — if any camera fails, recording finalizes gracefully
14. **Audio recording** — optional, controlled by `mic_device_index` (future scope)
15. **Recording folder schema** — identical directory layout for frontend compatibility

---

## Confirmed Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Prefer pure Rust, ffmpeg as fallback** | Try to avoid external process dependency if possible. If a pure Rust encoder (e.g., `openh264` crate, `mp4` crate) can match the quality and cross-platform support, use it. If not, ffmpeg is acceptable — potentially bundled with the build. |
| 2 | **Audit timestamps for Rust pipeline** | Don't just port the Python timestamp stages. The "copy to shared memory" stage is meaningless in a threaded Rust app. Do a full audit to determine which stages make sense for the new pipeline. This is Component #6. |
| 3 | **Timestamp storage: fixed struct for hot path → map for output** | Use a fixed struct in the hot loop (zero heap allocation, stack-only), convert to extensible map representation for CSV output and statistics. Best of both: fast in the loop, flexible at rest. |
| 4 | **RecordingFinalizer: sync, on blocking thread** | Run on `tokio::task::spawn_blocking` so the HTTP API stays responsive but the finalizer code itself is straightforward synchronous Rust. |
| 5 | **CSV streaming + Polars analysis** | Use the `csv` crate for streaming writes during recording (data lands on disk alongside video, resilient to crashes). Use `polars` for loading and analyzing the recorded data afterward. Both dependencies are acceptable. |