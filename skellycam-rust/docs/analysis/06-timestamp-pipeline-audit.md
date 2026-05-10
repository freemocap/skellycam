# Component #6: Timestamp Pipeline Audit & Rust Design

Status: **ANALYZED — stable reference artifact**

Files analyzed:
- `skellycam/core/camera/opencv/opencv_helpers/opencv_get_frame.py` — grab/retrieve timestamps
- `skellycam/core/camera/opencv/opencv_camera_loop.py` — frame lifecycle, SHM copy, recording timestamps
- `skellycam/core/timestamps/numpy_timestamps/process_recording_timestamps.py` — duration computation
- `skellycam/core/timestamps/numpy_timestamps/calculate_timestamps_numpy.py` — duration formulas
- `skellycam/core/timestamps/numpy_timestamps/create_camera_csvs.py` — per-camera CSV output
- `skellycam/core/timestamps/numpy_timestamps/create_multi_frame_csvs.py` — multiframe CSV + cross-camera stats
- `skellycam/core/timestamps/recording_timestamp_stats.py` — statistics struct
- `skellycam/core/timestamps/timebase_mapping.py` — perf_counter → UTC conversion
- `skellycam/core/timestamps/full_timestamp.py` — FullTimestamp (UTC + local + perf_counter)
- `skellycam/core/types/numpy_record_dtypes.py` — all dtype definitions
- `skellycam/core/recorders/videos/video_recorder.py` — record timestamps

---

## Part 1: Exact Python Timestamp Map

Every `time.perf_counter_ns()` call site in the hot path, in execution order:

### Camera Thread (single loop iteration)

```
Step 1: initialize_frame_recarray()          ← END of PREVIOUS iteration
  initialized_ns = time.perf_counter_ns()
  (also zeros out all other timestamp fields)

Step 2: opencv_get_frame()
  pre_frame_grab_ns   = time.perf_counter_ns()
  cap.grab()                                   ← USB driver dequeue
  post_frame_grab_ns  = time.perf_counter_ns()
  
  pre_frame_retrieve_ns  = time.perf_counter_ns()
  cap.retrieve(image=...)                      ← MJPEG→BGR decode into pre-allocated buffer
  post_frame_retrieve_ns = time.perf_counter_ns()

Step 3: camera loop (after grab/retrieve)
  pre_copy_to_camera_shm_ns  = time.perf_counter_ns()
  camera_shm.put_frame(...)                    ← numpy copy to shared memory
  post_copy_to_camera_shm_ns = time.perf_counter_ns()

Step 4: video_recorder.record_frame()  (if recording)
  pre_frame_record_ns   = time.perf_counter_ns()
  cv2.VideoWriter.write(image)                 ← encode + write to file
  post_frame_record_ns  = time.perf_counter_ns()
```

### Duration Computation (from these 9 timestamps)

```
idle_before_frame_grab      = pre_grab - initialized
during_frame_grab            = post_grab - pre_grab
idle_before_retrieve         = pre_retrieve - post_grab
during_frame_retrieve        = post_retrieve - pre_retrieve
idle_before_copy_to_shm      = pre_copy_to_shm - post_retrieve
during_copy_to_shm           = post_copy_to_shm - pre_copy_to_shm
idle_before_frame_record     = pre_record - post_copy_to_shm
during_frame_record          = post_record - pre_record
total_frame_processing_time  = during_grab + during_retrieve + during_copy + during_record
                               + idle_before_retrieve + idle_before_copy + idle_before_record
total_camera_idle_time       = idle_before_frame_grab
```

### The "frame main timestamp" (used for multiframe synchronization)

```python
frame_main_timestamp_ns = (pre_frame_grab_ns + post_frame_grab_ns) // 2
```

This midpoint is the best available proxy for "when were these photons captured." It's used for:
- Per-camera frame timestamp (the primary timestamp for each frame)
- Framerate calculation (`1.0 / diff(consecutive_main_timestamps)`)
- Inter-camera sync measurement (`max(main_timestamps) - min(main_timestamps)` across cameras at same frame number)

### TimebaseMapping

Maps `perf_counter_ns` (arbitrary origin, monotonic) to `utc_time_ns` (Unix epoch):
```python
unix_ns = timebase.utc_time_ns + (perf_counter_ns - timebase.perf_counter_ns)
```
Captured once at camera group startup, embedded in every frame's metadata recarray. This lets any timestamp be converted to UTC after the fact.

---

## Part 2: Audit — What Changes for Rust Threaded Pipeline

### Structural Differences

| Python Concept | Rust Equivalent | Effect on Timestamps |
|---------------|-----------------|---------------------|
| Single camera process per camera | Camera thread + decoder thread per camera | Timestamps span 3+ threads instead of 1 |
| `multiprocessing.Value` shared counters | `Arc<AtomicI64>` | Same semantics, no copy |
| numpy shared memory ring buffer | `tokio::sync::watch` / `mpsc` channels | No "copy to SHM" step; `Arc` ref bump instead |
| `cv2.VideoWriter` per camera | ffmpeg subprocess (or pure Rust encoder) per camera | Different timing characteristics |
| `time.perf_counter_ns()` | `std::time::Instant::now()` or raw `perf_counter` | Same underlying OS clock on most platforms |
| 9 timestamps per frame | Fewer stages, but inter-thread gaps become measurable | Some stages removed, new measurement opportunities |

### Stages to REMOVE

**`pre_copy_to_camera_shm_ns` / `post_copy_to_camera_shm_ns`**

Reason: There is no shared memory copy in Rust. Threads share address space. The "publish" operation is `Arc::clone()` + `send_replace()` on a watch channel — a reference count bump and an atomic pointer swap, ~10-20ns total. Wrapping this in timestamps would measure noise. Remove these fields.

**`initialized_ns`**

Reason: In Python, `initialized_ns` marks the boundary between "end of previous frame's recording/checks" and "start of next frame's idle." With structural backpressure, there is no per-iteration reset — the camera thread blocks on `sync_channel::send()` and unblocks when the gatherer calls `recv()`. The idle period is implicit in the channel blocking time. We don't need to timestamp it explicitly.

That said, the **gap between iterations** is still valuable. In Rust, this becomes:
```
iteration_gap = current_frame.pre_frame_grab - previous_frame.post_frame_grab
```
This tells us how long the camera thread was waiting on backpressure. We can compute it from existing timestamps without a dedicated `initialized_ns` field.

### Stages to RENAME/RECONCEPTUALIZE

**`pre_frame_retrieve_ns` / `post_frame_retrieve_ns` → `pre_frame_decode_ns` / `post_frame_decode_ns`**

Reason: In OpenCV, `retrieve()` decodes the raw frame (MJPEG → BGR). In nokhwa, the equivalent is decoding the raw buffer. On the decoder thread, this is the primary operation. "Decode" is the more general term and applies regardless of the underlying camera API.

### Stages that STAY

**`pre_frame_grab_ns` / `post_frame_grab_ns`** — On the camera thread, bracketing the raw frame acquisition.

**`pre_frame_record_ns` / `post_frame_record_ns`** — On the recorder thread, bracketing the ffmpeg stdin write.

### New Measurement: Inter-Thread Gaps

The structural backpressure pipeline creates measurable gaps between threads:

```
camera thread       decoder thread        gatherer              recorder thread
pre_grab            pre_decode                                  
post_grab ──gap1──→ post_decode ──gap2──→ [fanout] ──gap3──→ pre_record
                                                              post_record
```

- **gap1** = `pre_decode - post_grab`: Channel transfer latency + decoder queue wait. Reveals whether the decoder is keeping up with the camera.
- **gap2** = `gatherer_recv_time - post_decode`: Gatherer synchronization wait. How long this camera's decoded frame sat waiting for other cameras to catch up.
- **gap3** = `pre_record - gatherer_send_time`: Recorder queue drain time. Whether the recorder is falling behind.

These aren't additional timestamp fields — they're computed from the existing stages. With timestamps on different threads collected into the same `FrameTimestamps` struct, we get inter-thread gap analysis for free.

---

## Part 3: Proposed Rust Timestamp Design

### Hot-Path Struct (stack-allocated, zero heap)

```rust
/// Timestamps for a single frame's journey through the pipeline.
/// Stack-allocated, no heap — safe to create/drop in the hot loop.
#[derive(Debug, Clone, Copy)]
pub struct FrameTimestamps {
    // --- Camera thread (grab only) ---
    pub pre_frame_grab_nanoseconds: i64,
    pub post_frame_grab_nanoseconds: i64,

    // --- Decoder thread ---
    pub pre_frame_decode_nanoseconds: i64,
    pub post_frame_decode_nanoseconds: i64,

    // --- Recorder thread ---
    pub pre_frame_record_nanoseconds: i64,
    pub post_frame_record_nanoseconds: i64,
}
```

This is a fixed struct for the hot path — no allocations, no indirection, trivially `Copy`. The camera thread fills in its two fields. The decoder thread fills in its two. The recorder thread fills in its two. The full struct is assembled when all stages complete.

### Why a Fixed Struct for the Hot Path

- **Zero allocation**: 6 × i64 = 48 bytes on the stack. A `BTreeMap` would allocate on the heap per frame.
- **Predictable layout**: The compiler knows exact sizes. No pointer chasing.
- **Send + Sync + Copy**: Trivially safe to pass through channels.
- **The hot path doesn't need extensibility**: The camera loop always does grab→decode→record. Only 3 operations.

### Extensible Representation for Storage and Output

For CSV output, statistics, and future pipeline stages, convert to a map-based representation:

```rust
/// A stage in the frame processing pipeline.
/// Ordered by execution sequence (derive Ord).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum TimestampStage {
    // --- Core camera pipeline (in execution order) ---
    PreFrameGrab,
    PostFrameGrab,
    PreFrameDecode,
    PostFrameDecode,
    PreFrameRecord,
    PostFrameRecord,

    // --- Future stages (add here as needed) ---
    // PreFrameRotation,
    // PostFrameRotation,
    // PreJpegEncode,
    // PostJpegEncode,
    // PreWebsocketSend,
    // PostWebsocketSend,
    // PreRealTimeTracker,
    // PostRealTimeTracker,
}

impl TimestampStage {
    /// Human-readable name for CSV columns and statistics display.
    pub fn display_name(self) -> &'static str {
        match self {
            Self::PreFrameGrab => "pre_frame_grab",
            Self::PostFrameGrab => "post_frame_grab",
            Self::PreFrameDecode => "pre_frame_decode",
            Self::PostFrameDecode => "post_frame_decode",
            Self::PreFrameRecord => "pre_frame_record",
            Self::PostFrameRecord => "post_frame_record",
        }
    }

    /// Whether this is a "pre" marker (vs "post").
    pub fn is_pre(self) -> bool {
        matches!(self,
            Self::PreFrameGrab | Self::PreFrameDecode | Self::PreFrameRecord
        )
    }

    /// The matching post stage for a pre stage (and vice versa).
    pub fn pair(self) -> TimestampStage {
        match self {
            Self::PreFrameGrab => Self::PostFrameGrab,
            Self::PostFrameGrab => Self::PreFrameGrab,
            Self::PreFrameDecode => Self::PostFrameDecode,
            Self::PostFrameDecode => Self::PreFrameDecode,
            Self::PreFrameRecord => Self::PostFrameRecord,
            Self::PostFrameRecord => Self::PreFrameRecord,
        }
    }
}
```

### Conversion: Fixed Struct → Extensible Map

```rust
impl FrameTimestamps {
    /// Convert the hot-path struct into an extensible map for storage/analysis.
    pub fn to_stage_map(&self) -> BTreeMap<TimestampStage, i64> {
        let mut map = BTreeMap::new();
        map.insert(TimestampStage::PreFrameGrab, self.pre_frame_grab_nanoseconds);
        map.insert(TimestampStage::PostFrameGrab, self.post_frame_grab_nanoseconds);
        map.insert(TimestampStage::PreFrameDecode, self.pre_frame_decode_nanoseconds);
        map.insert(TimestampStage::PostFrameDecode, self.post_frame_decode_nanoseconds);
        map.insert(TimestampStage::PreFrameRecord, self.pre_frame_record_nanoseconds);
        map.insert(TimestampStage::PostFrameRecord, self.post_frame_record_nanoseconds);
        map
    }
}
```

### Duration Computation (Generic Over Stages)

Instead of hardcoding each duration field name, compute durations generically from the ordered stage list:

```rust
/// Computed durations for a single frame.
pub struct FrameDurations {
    /// Duration of each stage: "during_frame_grab_nanoseconds", etc.
    pub stage_durations: BTreeMap<String, i64>,
    /// Idle/gap time before each stage: "idle_before_frame_decode_nanoseconds", etc.
    pub idle_durations: BTreeMap<String, i64>,
    /// End-to-end: post_record - pre_grab
    pub total_processing_nanoseconds: i64,
}

impl FrameDurations {
    pub fn compute(timestamps: &BTreeMap<TimestampStage, i64>) -> Self {
        let stages: Vec<(TimestampStage, i64)> = timestamps.iter()
            .map(|(&stage, &ns)| (stage, ns))
            .collect();

        let mut stage_durations = BTreeMap::new();
        let mut idle_durations = BTreeMap::new();

        for window in stages.windows(2) {
            let ((stage_a, ns_a), (stage_b, ns_b)) = (window[0], window[1]);
            let duration = ns_b - ns_a;

            if stage_a.is_pre() && stage_b == stage_a.pair() {
                // These are a pre/post pair → "during" duration
                let base = stage_a.display_name().strip_prefix("pre_").unwrap();
                stage_durations.insert(
                    format!("during_{}_nanoseconds", base),
                    duration,
                );
            } else {
                // These cross a stage boundary → "idle" or "gap" duration
                idle_durations.insert(
                    format!("gap_before_{}_nanoseconds", stage_b.display_name()),
                    duration,
                );
            }
        }

        let total = timestamps.get(&TimestampStage::PostFrameRecord)
            .and_then(|&post| {
                timestamps.get(&TimestampStage::PreFrameGrab)
                    .map(|&pre| post - pre)
            })
            .unwrap_or(0);

        Self {
            stage_durations,
            idle_durations,
            total_processing_nanoseconds: total,
        }
    }
}
```

**Key design property**: Adding a new `TimestampStage` variant automatically produces corresponding duration and idle columns in the output. No changes to `FrameDurations::compute()` needed. The output CSV gets new columns without breaking existing ones.

### Recorded Frame Metadata

```rust
/// Full metadata for a recorded frame, stored per camera during recording.
#[derive(Debug, Clone)]
pub struct RecordedFrameMetadata {
    pub camera_identifier: String,
    pub camera_index: i32,
    pub frame_number: i64,
    pub timebase_mapping: TimebaseMapping,
    pub timestamps: FrameTimestamps,
}
```

This accumulates in a `Vec<RecordedFrameMetadata>` on each recorder. After recording stops, the finalizer processes all cameras' metadata.

---

## Part 4: CSV Output Design

### Streaming Write (during recording)

Use the `csv` crate to write per-camera timestamp rows as frames are recorded:

```rust
use csv::Writer;

struct TimestampCsvWriter {
    writer: Writer<File>,
}

impl TimestampCsvWriter {
    fn write_frame(
        &mut self,
        recording_frame_number: i64,
        connection_frame_number: i64,
        timestamps: &FrameTimestamps,
        durations: &FrameDurations,
        timebase: &TimebaseMapping,
        recording_start_nanoseconds: i64,
    ) -> Result<()> {
        let grab_midpoint = (timestamps.pre_frame_grab_nanoseconds
            + timestamps.post_frame_grab_nanoseconds) / 2;

        self.writer.serialize(PerCameraCsvRow {
            recording_frame_number,
            connection_frame_number,
            timestamp_from_recording_start_seconds: nanoseconds_to_seconds(
                grab_midpoint - recording_start_nanoseconds,
            ),
            timestamp_perf_counter_nanoseconds: grab_midpoint,
            // ... all timestamp and duration fields
        })?;
        Ok(())
    }
}
```

The streaming approach means timestamps land on disk alongside the video. If the process crashes mid-recording, the CSV contains all frames up to the crash — no data loss.

### Polars for Post-Recording Analysis

After recording finishes, load all per-camera CSVs into `polars` DataFrames for:

1. **Multi-frame assembly**: Join all cameras' DataFrames on `connection_frame_number`
2. **Cross-camera statistics**: Compute mean, median, std, range across cameras per frame
3. **Inter-camera sync**: `max(grab_midpoint) - min(grab_midpoint)` per multiframe
4. **Statistics summary**: For each duration column, compute global statistics
5. **Multi-frame CSV output**: Write the combined DataFrame with per-frame cross-camera stats

```rust
use polars::prelude::*;

fn build_multiframe_dataframe(
    camera_dataframes: &HashMap<String, DataFrame>,
    recording_start_nanoseconds: i64,
) -> PolarsResult<DataFrame> {
    // Join all cameras' data on frame_number
    // Compute cross-camera statistics per frame
    // Build the multi-frame CSV structure
}
```

### CSV Column Naming Convention

Full names, no abbreviations, consistent with the user's code style:

| Python Column | Rust Column |
|--------------|-------------|
| `frame.initialized.ns` | REMOVED (no equivalent in Rust pipeline) |
| `frame.pre_frame_grab.ns` | `frame.pre_grab.nanoseconds` |
| `frame.post_frame_grab.ns` | `frame.post_grab.nanoseconds` |
| `frame.pre_frame_retrieve.ns` | `frame.pre_decode.nanoseconds` |
| `frame.post_frame_retrieve.ns` | `frame.post_decode.nanoseconds` |
| `frame.pre_copy_to_camera_shm.ns` | REMOVED (no SHM copy in Rust) |
| `frame.post_copy_to_camera_shm.ns` | REMOVED |
| `frame.pre_frame_record.ns` | `frame.pre_record.nanoseconds` |
| `frame.post_frame_record.ns` | `frame.post_record.nanoseconds` |
| `duration.idle_before_frame_grab.ns` | `duration.gap_before_grab.nanoseconds` |
| `duration.during_frame_grab.ns` | `duration.during_grab.nanoseconds` |
| `duration.idle_before_retrieve.ns` | `duration.gap_before_decode.nanoseconds` |
| `duration.during_frame_retrieve.ns` | `duration.during_decode.nanoseconds` |
| `duration.idle_before_copy_to_camera_shm.ns` | REMOVED |
| `duration.during_copy_to_camera_shm.ns` | REMOVED |
| `duration.idle_before_frame_record.ns` | `duration.gap_before_record.nanoseconds` |
| `duration.during_frame_record.ns` | `duration.during_record.nanoseconds` |
| `total.frame_processing_time.ns` | `total.processing.nanoseconds` |
| `total.camera_idle_time.ns` | REMOVED (replaced by per-stage gap durations) |

Note: "nanoseconds" is written out fully (user rule: no abbreviations).

---

## Part 5: Timebase Mapping in Rust

The `TimebaseMapping` concept carries over cleanly:

```rust
/// Maps the arbitrary `perf_counter` timebase to UTC Unix time.
/// Captured once at camera group startup.
#[derive(Debug, Clone, Copy)]
pub struct TimebaseMapping {
    /// The UTC time in nanoseconds when this mapping was created.
    pub utc_time_nanoseconds: i64,
    /// The perf_counter value at the same instant.
    pub perf_counter_nanoseconds: i64,
    /// Offset from UTC to local time, in seconds.
    pub local_time_utc_offset_seconds: i32,
}

impl TimebaseMapping {
    /// Create a new mapping at the current instant.
    pub fn capture() -> Self {
        Self {
            utc_time_nanoseconds: unix_time_nanoseconds(),
            perf_counter_nanoseconds: performance_counter_nanoseconds(),
            local_time_utc_offset_seconds: local_utc_offset_seconds(),
        }
    }

    /// Convert a perf_counter timestamp to Unix nanoseconds.
    pub fn to_unix_nanoseconds(&self, perf_counter: i64, local_time: bool) -> i64 {
        let unix = self.utc_time_nanoseconds
            + (perf_counter - self.perf_counter_nanoseconds);
        if local_time {
            unix + (self.local_time_utc_offset_seconds as i64 * 1_000_000_000)
        } else {
            unix
        }
    }
}
```

`std::time::Instant` is opaque — it doesn't expose the raw counter value and can't be converted to/from integers. For timestamp logging, we need raw integer nanoseconds. Options:

- `std::time::Instant::now().duration_since(START)` → lose the UTC mapping
- `libc::clock_gettime(CLOCK_MONOTONIC)` → raw i64, same as Python's `time.perf_counter_ns()`
- Cross-platform crate like `instant` or `web-time`

Given we're targeting desktop only (Windows, macOS, Linux), `libc::clock_gettime` or `std::time::Instant` with a captured origin both work. The key requirement: a monotonic i64 nanosecond counter that can be mapped to UTC.

---

## Part 6: Statistics (Replacing RecordingTimestampsStats)

Instead of a fixed struct with 24+ named fields, use a map-driven approach:

```rust
/// Statistics for a single metric across all frames.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricStatistics {
    pub mean: f64,
    pub median: f64,
    pub standard_deviation: f64,
    pub coefficient_of_variation: f64,
    pub minimum: f64,
    pub maximum: f64,
    pub range: f64,
}

/// Complete recording timestamp statistics.
/// Generic over which stages/durations exist — adding a new stage
/// automatically produces statistics for it.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecordingTimestampStatistics {
    pub recording_name: String,
    pub number_of_cameras: usize,
    pub number_of_frames: usize,
    pub total_duration_seconds: f64,

    /// Framerate statistics (Hz).
    pub framerate: MetricStatistics,

    /// Frame duration statistics (milliseconds).
    pub frame_duration: MetricStatistics,

    /// Inter-camera frame grab synchronization (milliseconds).
    pub inter_camera_grab_range: MetricStatistics,

    /// Per-stage statistics, keyed by stage name.
    /// e.g., "during_grab" → MetricStatistics, "gap_before_decode" → MetricStatistics
    pub stage_statistics: BTreeMap<String, MetricStatistics>,
}
```

The stage_statistics map is populated by iterating over all stages present in the data. Adding a new TimestampStage variant automatically produces a new entry in this map.

---

## Functionality That Must Be Preserved

1. **Perf_counter → UTC mapping** — captured once at startup, embedded in every frame
2. **Frame grab midpoint as primary timestamp** — `(pre_grab + post_grab) / 2`
3. **Framerate from consecutive grab midpoints** — `1.0 / diff(timestamps)`
4. **Inter-camera sync measurement** — max grab midpoint range across cameras per multiframe
5. **Per-frame per-camera CSV** — one file per camera, all timestamp and duration columns
6. **Multi-frame CSV** — combined with cross-camera statistics per frame
7. **Statistics summary** — median, mean, std, min, max for all metrics
8. **Human-readable statistics report** — text output with formatted tables
9. **JSON statistics** — machine-readable format
10. **RecordingInfo JSON** — recording metadata saved alongside timestamps

---

## Open Question

| # | Question | Notes |
|---|----------|-------|
| 1 | Raw perf_counter access for integer timestamps | `std::time::Instant` is opaque (no integer conversion). Need `libc::clock_gettime` or a crate like `perf-event` for raw i64. Or use `Instant::now().duration_since(Instant::now() - Duration::from_nanos(0))` trick. Python's `time.perf_counter_ns()` returns raw i64 — we need equivalent. |
