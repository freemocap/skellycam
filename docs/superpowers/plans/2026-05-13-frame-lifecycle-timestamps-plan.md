# Frame Lifecycle Timestamps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument every meaningful point in the frame capture pipeline with nanosecond-precision monotonic timestamps, replace the single `grab_timestamp_nanoseconds` field with a full `FrameLifecycleTimestamps` struct, and compute per-stage duration breakdowns in the gatherer statistics.

**Architecture:** A `FrameLifecycleTimestamps` struct (9 `i64` nanosecond fields) is carried on every `FramePacket`. The camera thread stamps 8 fields; the gatherer stamps the 9th after `recv()`. `MultiFramePayload` gets 4 payload-level timestamp fields. Derived durations (hardware wait, barrier sync, capture duration, channel backpressure, etc.) are computed in the gatherer's final statistics output, not stored.

**Tech Stack:** Rust, `std::time::Instant` via `performance_counter_nanoseconds()`, structural backpressure pipeline

---

## File Modification Map

| File | What Changes |
|------|--------------|
| `src/camera/types.rs` | Add `FrameLifecycleTimestamps`. Replace `grab_timestamp_nanoseconds` on `FramePacket`. Add payload timestamp fields to `MultiFramePayload`. Update `inter_camera_grab_spread_nanoseconds()` to use `frame_available_ns`. |
| `src/camera/thread.rs` | Stamp all 8 camera-side timestamps. Build `FramePacket` with `FrameLifecycleTimestamps`. |
| `src/camera_group/gatherer.rs` | Stamp `gatherer_received_ns` on each frame after recv. Stamp 4 payload timestamps. Replace stats output with per-stage duration breakdown. |
| `src/timestamps/csv_writer.rs` | Replace `write_row(frame_number, grab_ts, recorded_ts)` with a method that takes `&FrameLifecycleTimestamps` and writes all 9 timestamp columns. |
| `src/main.rs` | Update all references from `grab_timestamp_nanoseconds` to `timestamps.pre_capture_ns`. Update recording mode to pass full timestamps to CsvWriter. |

---

### Task 1: Add FrameLifecycleTimestamps struct and update types

**Files:**
- Modify: `skellycam-rust/skellycam/src/camera/types.rs`

- [ ] **Step 1: Add FrameLifecycleTimestamps struct and update FramePacket**

Replace the entire contents of `src/camera/types.rs` with:

```rust
//! Camera channel protocol types.

use std::sync::mpsc;

/// All nanosecond-precision monotonic timestamps in a single frame's lifecycle.
///
/// The camera thread stamps fields prefixed `camera_*` as the frame moves
/// through the capture loop. The gatherer stamps `gatherer_received_ns` after
/// `recv()` returns. All values are from `performance_counter_nanoseconds()` —
/// nanoseconds since process start. Zero means "not yet stamped."
#[derive(Debug, Clone)]
pub struct FrameLifecycleTimestamps {
    /// Top of the capture loop iteration for this frame.
    pub loop_start_ns: i64,
    /// `Cap_hasNewFrame()` returned true — hardware has a frame ready.
    pub frame_available_ns: i64,
    /// About to call `barrier.wait()`.
    pub pre_barrier_ns: i64,
    /// Barrier released — all cameras and gatherer synchronized.
    pub post_barrier_ns: i64,
    /// About to call `Cap_captureFrame()`.
    pub pre_capture_ns: i64,
    /// `Cap_captureFrame()` returned successfully.
    pub post_capture_ns: i64,
    /// About to call `frame_sender.send()`.
    pub pre_send_ns: i64,
    /// `frame_sender.send()` returned — gatherer consumed previous frame,
    /// channel has capacity for this one.
    pub post_send_ns: i64,
    /// Stamped by the gatherer when `recv()` returns this frame.
    pub gatherer_received_ns: i64,
}

impl FrameLifecycleTimestamps {
    pub fn new() -> Self {
        Self {
            loop_start_ns: 0,
            frame_available_ns: 0,
            pre_barrier_ns: 0,
            post_barrier_ns: 0,
            pre_capture_ns: 0,
            post_capture_ns: 0,
            pre_send_ns: 0,
            post_send_ns: 0,
            gatherer_received_ns: 0,
        }
    }
}

/// Frame pixel data format.
#[derive(Debug, Clone)]
pub enum FrameData {
    Rgb(Vec<u8>),
}

impl FrameData {
    pub fn len(&self) -> usize {
        match self {
            Self::Rgb(bytes) => bytes.len(),
        }
    }

    pub fn as_bytes(&self) -> &[u8] {
        match self {
            Self::Rgb(bytes) => bytes,
        }
    }
}

/// A single camera frame traveling through the pipeline.
#[derive(Debug, Clone)]
pub struct FramePacket {
    pub data: FrameData,
    pub width: u32,
    pub height: u32,
    pub timestamps: FrameLifecycleTimestamps,
    pub identity: CameraIdentity,
    pub frame_number: i64,
}

/// Three-part camera identification.
#[derive(Debug, Clone)]
pub struct CameraIdentity {
    pub display_name: String,
    pub camera_index: i32,
    pub unique_identifier: String,
    pub device_path: String,
}

impl CameraIdentity {
    pub fn label(&self) -> String {
        format!("{} [{}]", self.display_name, self.unique_identifier)
    }
}

/// Multi-camera synchronized payload with gatherer-level timestamps.
#[derive(Debug)]
pub struct MultiFramePayload {
    pub frames: Vec<FramePacket>,
    pub step: i64,
    /// Stamped when the last camera's `recv()` completes.
    pub all_frames_received_ns: i64,
    /// Stamped after the `MultiFramePayload` struct is assembled.
    pub payload_assembled_ns: i64,
    /// Stamped just before `multi_frame_sender.send()`.
    pub pre_send_downstream_ns: i64,
    /// Stamped after `send()` returns to the downstream consumer.
    pub post_send_downstream_ns: i64,
}

impl MultiFramePayload {
    /// Inter-camera synchronization spread measured at the point when
    /// hardware reported each frame available. This is the physically
    /// meaningful sync metric — when did each camera's sensor actually
    /// have a frame ready, not when did our software thread read the clock.
    pub fn inter_camera_grab_spread_nanoseconds(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let min = self
            .frames
            .iter()
            .map(|f| f.timestamps.frame_available_ns)
            .min()
            .unwrap();
        let max = self
            .frames
            .iter()
            .map(|f| f.timestamps.frame_available_ns)
            .max()
            .unwrap();
        max - min
    }
}

#[derive(Debug)]
pub enum CameraCommand {
    Shutdown,
}

#[derive(Debug)]
pub enum CameraEvent {
    Error(String),
}

#[derive(Debug, Clone)]
pub struct CameraHandle {
    pub command_sender: mpsc::Sender<CameraCommand>,
    pub identity: CameraIdentity,
    pub width: u32,
    pub height: u32,
}

impl CameraHandle {
    pub fn send_shutdown(&self) {
        let _ = self.command_sender.send(CameraCommand::Shutdown);
    }
}
```

- [ ] **Step 2: Build to verify types compile**

Run:
```
cargo build --release 2>&1
```

Expected: compilation errors in `thread.rs`, `gatherer.rs`, `main.rs`, `csv_writer.rs` (expected — those files still reference the old field names). This confirms the type changes are correct and the rest of the code needs updating.

---

### Task 2: Stamp all camera-side timestamps in the capture loop

**Files:**
- Modify: `skellycam-rust/skellycam/src/camera/thread.rs`

- [ ] **Step 1: Update imports and FramePacket construction**

In `src/camera/thread.rs`, change the import line (line 14):

```rust
use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket};
```

to:

```rust
use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket, FrameLifecycleTimestamps};
```

- [ ] **Step 2: Rewrite the capture loop with all 8 timestamp stamps**

Replace lines 110-189 (the `loop` block in `run_camera_thread`) with:

```rust
        loop {
            // ── loop_start_ns ──
            let loop_start_ns = performance_counter_nanoseconds();

            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown");
                break;
            }

            // Spin-wait for next hardware frame
            let wait_start = std::time::Instant::now();
            loop {
                if check_shutdown(command_receiver) {
                    tracing::info!("Camera {label}: shutdown during hasNewFrame");
                    Cap_closeStream(ctx, stream);
                    Cap_releaseContext(ctx);
                    return Ok(());
                }
                if Cap_hasNewFrame(ctx, stream) != 0 {
                    break;
                }
                std::thread::yield_now();
                if wait_start.elapsed().as_secs() > 5 {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Camera {label}: timeout waiting for frame {frame_number}"
                    )));
                    Cap_closeStream(ctx, stream);
                    Cap_releaseContext(ctx);
                    return Ok(());
                }
            }

            // ── frame_available_ns ──
            let frame_available_ns = performance_counter_nanoseconds();

            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown before barrier");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            // ── pre_barrier_ns ──
            let pre_barrier_ns = performance_counter_nanoseconds();

            if !barrier.wait() {
                tracing::info!("Camera {label}: barrier broken (shutdown)");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            // ── post_barrier_ns ──
            let post_barrier_ns = performance_counter_nanoseconds();

            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown after barrier");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            // ── pre_capture_ns ──
            let pre_capture_ns = performance_counter_nanoseconds();

            let result = Cap_captureFrame(ctx, stream, buffer.as_mut_ptr(), frame_bytes as u32);

            // ── post_capture_ns ──
            let post_capture_ns = performance_counter_nanoseconds();

            if result != CAPRESULT_OK {
                let _ = event_sender.send(CameraEvent::Error(format!(
                    "Camera {label}: captureFrame failed at frame {frame_number} ({})",
                    result_name(result)
                )));
                break;
            }

            let packet = FramePacket {
                data: FrameData::Rgb(buffer.clone()),
                width: actual_width,
                height: actual_height,
                timestamps: FrameLifecycleTimestamps {
                    loop_start_ns,
                    frame_available_ns,
                    pre_barrier_ns,
                    post_barrier_ns,
                    pre_capture_ns,
                    post_capture_ns,
                    pre_send_ns: 0,  // stamped below, after this struct is built
                    post_send_ns: 0,  // stamped below
                    gatherer_received_ns: 0,  // stamped by gatherer
                },
                identity: identity.clone(),
                frame_number,
            };

            // ── pre_send_ns ──
            let pre_send_ns = performance_counter_nanoseconds();

            frame_number += 1;

            let mut send_packet = packet;
            send_packet.timestamps.pre_send_ns = pre_send_ns;

            if frame_sender.send(send_packet).is_err() {
                break;
            }

            // post_send_ns = right now
            // (FramePacket is consumed by the channel — we can't stamp it.
            //  The gatherer could back-calculate from gatherer_received_ns
            //  minus an estimate, or we could restructure. For now,
            //  we do NOT stamp post_send_ns inside the camera thread.)
        }
```

- [ ] **Step 3: Build to verify camera thread compiles**

Run:
```
cargo build --release 2>&1
```

Expected: errors only in `gatherer.rs`, `main.rs`, `csv_writer.rs` (camera thread should compile cleanly now).

---

### Task 3: Stamp gatherer-side timestamps and add duration breakdown stats

**Files:**
- Modify: `skellycam-rust/skellycam/src/camera_group/gatherer.rs`

- [ ] **Step 1: Update imports**

Change line 6 from:
```rust
use crate::camera::{CameraEvent, CameraHandle, FramePacket, MultiFramePayload};
```
to:
```rust
use crate::camera::{CameraEvent, CameraHandle, FramePacket, MultiFramePayload};
use crate::timestamps::performance::performance_counter_nanoseconds;
```

- [ ] **Step 2: Add duration tracking vectors**

After the existing let bindings in `spawn_gatherer` (after `let mut prev_multiframe_ts: Option<i64> = None;`), add:

```rust
        // Duration tracking per stage (in nanoseconds, computed each step)
        let mut duration_hardware_wait: Vec<f64> = Vec::new();
        let mut duration_barrier_sync: Vec<f64> = Vec::new();
        let mut duration_capture: Vec<f64> = Vec::new();
        let mut duration_channel_backpressure: Vec<f64> = Vec::new();
        let mut duration_gatherer_recv: Vec<f64> = Vec::new();
        let mut duration_total_iteration: Vec<f64> = Vec::new();
```

- [ ] **Step 3: Rewrite the gatherer loop body**

Replace lines 65-163 (the loop body and stats output in `spawn_gatherer`) with:

```rust
        loop {
            if !barrier.wait() {
                eprintln!("[gatherer] barrier broken, shutting down");
                for handle in &camera_handles {
                    handle.send_shutdown();
                }
                break;
            }

            // Drain event channels
            for event_receiver in &event_receivers {
                while let Ok(event) = event_receiver.try_recv() {
                    match event {
                        CameraEvent::Error(message) => {
                            eprintln!("[ERROR] {message}");
                        }
                    }
                }
            }

            // Collect frames, stamp gatherer_received_ns on each
            let mut frames: Vec<FramePacket> = Vec::with_capacity(camera_count);
            let mut disconnected = false;
            let mut all_frames_received_ns: i64 = 0;

            for (index, receiver) in frame_receivers.iter().enumerate() {
                match receiver.recv() {
                    Ok(mut packet) => {
                        let recv_ns = performance_counter_nanoseconds();
                        packet.timestamps.gatherer_received_ns = recv_ns;
                        all_frames_received_ns = recv_ns;
                        frames.push(packet);
                    }
                    Err(_) => {
                        eprintln!("[gatherer] camera {index} disconnected at step {step}");
                        disconnected = true;
                        break;
                    }
                }
            }

            if disconnected {
                for handle in &camera_handles {
                    handle.send_shutdown();
                }
                break;
            }

            let payload_assembled_ns = performance_counter_nanoseconds();

            let mut payload = MultiFramePayload {
                frames,
                step,
                all_frames_received_ns,
                payload_assembled_ns,
                pre_send_downstream_ns: 0,
                post_send_downstream_ns: 0,
            };

            // ── Track inter-multiframe interval (using first frame's frame_available_ns) ──
            if let Some(prev_ts) = prev_multiframe_ts {
                if step > 0 {
                    if let Some(first) = payload.frames.first() {
                        let dt_ns = first.timestamps.frame_available_ns - prev_ts;
                        if dt_ns > 0 {
                            multiframe_interval_ns.push(dt_ns as f64);
                        }
                    }
                }
            }
            if let Some(first) = payload.frames.first() {
                prev_multiframe_ts = Some(first.timestamps.frame_available_ns);
            }

            // ── Track spread (from frame_available_ns — when hardware reported frame ready) ──
            let spread_ns = payload.inter_camera_grab_spread_nanoseconds() as f64;
            spread_values.push(spread_ns);

            // ── Compute per-camera FPS and per-stage durations ──
            for frame in &payload.frames {
                let label = format!("{}:{}", frame.identity.camera_index, frame.identity.unique_identifier);

                // Per-camera FPS from consecutive frame timestamps
                if let Some(&prev_ts) = prev_timestamps.get(&label) {
                    let dt_ns = (frame.timestamps.frame_available_ns - prev_ts) as f64;
                    if dt_ns > 0.0 {
                        let fps = 1_000_000_000.0 / dt_ns;
                        per_camera_fps.insert(label.clone(), fps);
                        if let Some(stats) = camera_stats.get_mut(&label) {
                            stats.intervals_ns.push(dt_ns);
                            stats.last_fps = fps;
                        }
                    }
                }
                prev_timestamps.insert(label, frame.timestamps.frame_available_ns);

                // ── Per-stage durations ──
                let ts = &frame.timestamps;
                if ts.loop_start_ns > 0 && ts.frame_available_ns > 0 {
                    duration_hardware_wait.push((ts.frame_available_ns - ts.loop_start_ns) as f64);
                }
                if ts.pre_barrier_ns > 0 && ts.post_barrier_ns > 0 {
                    duration_barrier_sync.push((ts.post_barrier_ns - ts.pre_barrier_ns) as f64);
                }
                if ts.pre_capture_ns > 0 && ts.post_capture_ns > 0 {
                    duration_capture.push((ts.post_capture_ns - ts.pre_capture_ns) as f64);
                }
                if ts.pre_send_ns > 0 && ts.gatherer_received_ns > 0 {
                    // channel backpressure: from when camera was ready to send
                    // until gatherer received it (includes recv() blocking)
                    duration_channel_backpressure.push((ts.gatherer_received_ns - ts.pre_send_ns) as f64);
                }
                if ts.loop_start_ns > 0 && ts.gatherer_received_ns > 0 {
                    duration_total_iteration.push((ts.gatherer_received_ns - ts.loop_start_ns) as f64);
                }
            }

            // ── Gatherer recv durations (per-camera) ──
            // The time between the last camera sending and gatherer receiving was
            // already captured in channel_backpressure. The gatherer's own recv
            // time for each frame is stamped individually.

            if step > 0 && step % 30 == 0 {
                let spread_us = spread_ns / 1_000.0;
                let fps_list: Vec<String> = camera_labels.iter()
                    .filter_map(|label| {
                        per_camera_fps.get(label).map(|fps| format!("[{label}]={fps:.1}fps"))
                    })
                    .collect();
                eprintln!(
                    "  step {step:>5} | spread={spread_us:>7.1}µs | {}",
                    fps_list.join(" | "),
                );
            }

            step += 1;

            let pre_send_downstream_ns = performance_counter_nanoseconds();
            payload.pre_send_downstream_ns = pre_send_downstream_ns;

            if multi_frame_sender.send(payload).is_err() {
                eprintln!("[gatherer] downstream disconnected, shutting down");
                for handle in &camera_handles {
                    handle.send_shutdown();
                }
                break;
            }
            // post_send_downstream_ns — cannot be stamped because payload was moved.
        }
```

- [ ] **Step 4: Replace the final statistics block**

Replace the entire "Final Statistics" block (lines 166-208) with:

```rust
        // ── Final Statistics ──
        if step > 0 {
            eprintln!();
            eprintln!("══════════════════════════════════════════════════════════════════════");
            eprintln!("  GATHERER FINAL STATISTICS");
            eprintln!("──────────────────────────────────────────────────────────────────────");
            eprintln!("  Total steps: {step} across {camera_count} camera(s)");
            eprintln!();
            eprintln!("  TIMESTAMP EXPLANATION:");
            eprintln!("  - spread: max-min frame_available_ns across cameras in one multiframe.");
            eprintln!("    (Measures when hardware reported each frame ready — the physically");
            eprintln!("     meaningful sync metric.)");
            eprintln!("  - multiframe fps: rate from consecutive multiframe timestamps.");
            eprintln!("  - per-camera fps: rate for each camera from consecutive frame timestamps.");
            eprintln!();
            eprintln!("  PER-STAGE DURATION BREAKDOWN");
            eprintln!("  ────────────────────────────");
            eprintln!();

            // Per-stage duration summaries
            compute_summary(&duration_hardware_wait, "hardware wait (loop_start → frame_available)", "ns");
            eprintln!();
            compute_summary(&duration_barrier_sync, "barrier sync (pre_barrier → post_barrier)", "ns");
            eprintln!();
            compute_summary(&duration_capture, "capture memcpy (pre_capture → post_capture)", "ns");
            eprintln!();
            compute_summary(&duration_channel_backpressure, "channel backpressure (pre_send → gatherer_received)", "ns");
            eprintln!();
            compute_summary(&duration_total_iteration, "total iteration (loop_start → gatherer_received)", "ns");
            eprintln!();

            // Per-camera FPS
            eprintln!("  PER-CAMERA FPS");
            eprintln!("  ──────────────");
            for label in &camera_labels {
                if let Some(stats) = camera_stats.get(label) {
                    let fps_values: Vec<f64> = stats.intervals_ns.iter()
                        .map(|dt_ns| 1_000_000_000.0 / dt_ns)
                        .collect();
                    compute_summary(&fps_values, &format!("[{label}] per-camera fps"), "fps");
                }
            }
            eprintln!();

            // Multiframe FPS
            let mf_fps: Vec<f64> = multiframe_interval_ns.iter()
                .map(|dt_ns| 1_000_000_000.0 / dt_ns)
                .collect();
            compute_summary(&mf_fps, "multiframe fps (from inter-multiframe intervals)", "fps");
            eprintln!();

            // Spread
            let spread_us: Vec<f64> = spread_values.iter().map(|ns| ns / 1_000.0).collect();
            compute_summary(&spread_us, "inter-camera grab spread", "µs");

            eprintln!();
            eprintln!("══════════════════════════════════════════════════════════════════════");
            eprintln!();
        }
```

---

### Task 4: Update CSV writer with full timestamp columns

**Files:**
- Modify: `skellycam-rust/skellycam/src/timestamps/csv_writer.rs`

- [ ] **Step 1: Rewrite CsvWriter**

Replace the entire contents of `src/timestamps/csv_writer.rs` with:

```rust
//! Streaming CSV writer: one row per frame, written during recording.
//!
//! Crash-resilient: data is flushed to disk alongside the video, so
//! timestamps survive even if the process exits before `finish()`.

use std::fs::File;
use std::path::PathBuf;

use anyhow::Context;

use crate::camera::FrameLifecycleTimestamps;

pub struct CsvWriter {
    writer: csv::Writer<File>,
    path: PathBuf,
    row_count: u64,
}

impl CsvWriter {
    /// Create a new CSV file at `path` and write the header row.
    /// Column names use full words with dot-separated hierarchy — no abbreviations.
    pub fn new(path: PathBuf) -> anyhow::Result<Self> {
        let writer = csv::Writer::from_path(&path)
            .context("Failed to create timestamp CSV file")?;

        let mut writer = writer;
        writer
            .write_record(&[
                "frame_number",
                "timestamps.loop_start_ns",
                "timestamps.frame_available_ns",
                "timestamps.pre_barrier_ns",
                "timestamps.post_barrier_ns",
                "timestamps.pre_capture_ns",
                "timestamps.post_capture_ns",
                "timestamps.pre_send_ns",
                "timestamps.post_send_ns",
                "timestamps.gatherer_received_ns",
            ])
            .context("Failed to write CSV header")?;
        writer
            .flush()
            .context("Failed to flush CSV header")?;

        Ok(Self {
            writer,
            path,
            row_count: 0,
        })
    }

    /// Append one row to the CSV file and flush immediately.
    /// Flushing on every write ensures crash-resilience at the cost of
    /// slightly higher I/O — acceptable at 30fps per camera.
    pub fn write_row(
        &mut self,
        frame_number: i64,
        timestamps: &FrameLifecycleTimestamps,
    ) -> anyhow::Result<()> {
        self.writer
            .write_record(&[
                frame_number.to_string(),
                timestamps.loop_start_ns.to_string(),
                timestamps.frame_available_ns.to_string(),
                timestamps.pre_barrier_ns.to_string(),
                timestamps.post_barrier_ns.to_string(),
                timestamps.pre_capture_ns.to_string(),
                timestamps.post_capture_ns.to_string(),
                timestamps.pre_send_ns.to_string(),
                timestamps.post_send_ns.to_string(),
                timestamps.gatherer_received_ns.to_string(),
            ])
            .context("Failed to write CSV row")?;
        self.writer.flush().context("Failed to flush CSV row")?;

        self.row_count += 1;
        Ok(())
    }

    pub fn row_count(&self) -> u64 {
        self.row_count
    }

    /// Flush and return the file path for later use by the finalizer.
    pub fn finish(mut self) -> anyhow::Result<PathBuf> {
        self.writer.flush().context("Failed to flush CSV on finish")?;
        Ok(self.path)
    }
}
```

---

### Task 5: Update main.rs references

**Files:**
- Modify: `skellycam-rust/skellycam/src/main.rs`

- [ ] **Step 1: Update recording mode — feed_frame and csv_writer calls**

Replace lines 294-313 (the recording loop's frame processing) with:

```rust
                let frame_ts = payload.frames.first()
                    .map(|f| f.timestamps.pre_capture_ns)
                    .unwrap_or(0);

                for (idx, frame) in payload.frames.iter().enumerate() {
                    if let (Some(recorder), Some(csv_writer)) =
                        (recorders.get_mut(idx), csv_writers.get_mut(idx))
                    {
                        let rgb_data = frame.data.as_bytes();
                        recorder.feed_frame(
                            rgb_data,
                            frame.frame_number,
                            frame.timestamps.pre_capture_ns,
                            frame_ts,
                        )?;
                        csv_writer.write_row(
                            frame.frame_number,
                            &frame.timestamps,
                        )?;
                    }
                }
```

- [ ] **Step 2: Update imports at top of main.rs**

After the `use skellycam::timestamps::CsvWriter;` line (or wherever it is), there are no import changes needed since CsvWriter is already imported by name. But verify the `use` block includes `FrameLifecycleTimestamps` if used directly. In this plan it isn't — `frame.timestamps` is a `FrameLifecycleTimestamps` reference but we pass `&frame.timestamps` to csv_writer which takes `&FrameLifecycleTimestamps`. The type is inferred.

No import changes needed in main.rs.

- [ ] **Step 3: Build to verify everything compiles**

Run:
```
cargo build --release 2>&1
```

Expected: clean compilation with no errors.

---

### Task 6: Run verification tests

**Files:** None (verification only)

- [ ] **Step 1: Test with 1 camera**

Run:
```
cargo run --release -- --manager 1 2>&1
```

Expected:
- Camera starts, capture loop runs, gatherer collects frames
- Gatherer stats output shows per-stage duration breakdown (all 5 stages)
- Shutdown is clean

- [ ] **Step 2: Test with 2 cameras**

Run:
```
cargo run --release -- --manager 2 2>&1
```

Expected:
- Both cameras in lockstep
- Inter-camera spread computed from `frame_available_ns`
- Per-stage duration breakdown for each camera
- Shutdown is clean

- [ ] **Step 3: Test with 4 cameras**

Run:
```
cargo run --release -- --manager 4 2>&1
```

Expected:
- All 4 cameras in lockstep
- Inter-camera spread < 1ms (median in microseconds)
- Per-stage duration breakdown with meaningful numbers
- Shutdown is clean

- [ ] **Step 4: Test recording mode with timestamp CSV output**

Run:
```
cargo run --release -- --record 1 2>&1
```

Expected:
- Recording completes with 1 camera
- Timestamp CSV file has 10 columns (frame_number + 9 timestamp fields)
- CSV rows == video frame count
- CSV values are non-zero (timestamps were actually stamped)
- recording_info.json written successfully
