//! Gatherer thread — collects one frame from each camera per cycle, hits the
//! barrier to release all cameras simultaneously, then assembles and sends a
//! `MultiFramePayload` downstream while cameras spin for their next frame.
//!
//! Also computes and prints per-cycle and aggregate timing statistics on exit.
//! The statistics block honors the two-loop structure of the pipeline:
//! per-camera lifecycle metrics (one row per camera plus an across-camera
//! summary) and a separate gatherer-loop section for the gatherer's own
//! per-iteration timings.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{Receiver, Sender};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::camera::{FramePacket, MultiFramePayload};
use crate::camera_group::sync_utils::BreakableBarrier;
use crate::timestamps::performance::{anchor_wall_clock_time, performance_counter_nanoseconds};

use super::camera_group::{GathererState, GathererStateMachine};

/// Number of leading multiframes excluded from statistics. Cameras open their
/// capture streams at staggered wall-clock times — the first few multiframes
/// are dominated by initialization order and are not representative of
/// steady-state behavior. Three is the minimum that gets us past the
/// off-by-one in `pre_barrier`/`post_barrier` attribution (see note in
/// per-camera per-frame stats below).
const STATS_WARMUP_MULTIFRAMES: i64 = 3;

/// Number of trailing multiframes excluded from statistics. Cameras may be in
/// the middle of being torn down during the final multiframe(s) and their
/// timings can be distorted by shutdown.
const STATS_COOLDOWN_MULTIFRAMES: usize = 1;

/// Maximum number of multiframes retained in the gatherer's lifecycle-stats
/// ring buffer. 300 multiframes ≈ 10 seconds at 30 fps — enough for a
/// representative sample without unbounded memory growth.
const STATS_RING_BUFFER_LIMIT: usize = 300;

/// Truncate a single stats Vec if it exceeds the ring-buffer limit.
/// Drops from the front so the most recent samples are retained.
fn truncate_ring<T>(v: &mut Vec<T>) {
    if v.len() > STATS_RING_BUFFER_LIMIT {
        let excess = v.len() - STATS_RING_BUFFER_LIMIT;
        v.drain(0..excess);
    }
}

/// Truncate a slice of per-camera stats Vecs.
fn truncate_ring_buffer<T>(vecs: &mut [Vec<T>]) {
    for v in vecs.iter_mut() {
        truncate_ring(v);
    }
}

// ── Statistics primitives ────────────────────────────────────────────────────

struct Stats {
    median: f64,
    mean: f64,
    std: f64,
    cv_pct: f64,
    min: f64,
    max: f64,
    n: usize,
}

fn compute_stats(values: &[f64]) -> Option<Stats> {
    if values.is_empty() {
        return None;
    }
    let n = values.len();
    let mut sorted: Vec<f64> = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let mean = values.iter().sum::<f64>() / n as f64;
    let median = sorted[n / 2];
    let min = sorted[0];
    let max = sorted[n - 1];
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
    let std = variance.sqrt();
    let cv_pct = if mean.abs() > f64::EPSILON {
        (std / mean) * 100.0
    } else {
        0.0
    };

    Some(Stats {
        median,
        mean,
        std,
        cv_pct,
        min,
        max,
        n,
    })
}

/// Choose a divisor and unit for an entire column of values (ns / µs / ms).
///
/// Uses the **maximum** value in the column, not the median. This ensures
/// that any value over 1000 µs in a column forces the whole column into ms,
/// preventing cases like `31446 µs` alongside `278 µs` in the same table.
fn auto_scale(values_ns: &[f64]) -> (f64, &'static str) {
    let max = values_ns.iter().cloned().fold(0.0_f64, f64::max);
    if max >= 1_000_000.0 {
        (1_000_000.0, "ms")
    } else if max >= 1_000.0 {
        (1_000.0, "µs")
    } else {
        (1.0, "ns")
    }
}

/// Format a single numeric value with its unit.
///
/// Always shows at least 2 decimal places for non-zero values so that
/// all cells in a column have consistent precision:
///   >= 10 000  → 1 decimal  (very large numbers; rare after max-based scaling)
///   >=     1   → 2 decimals
///   <      1   → 3 decimals (sub-unit precision, e.g. 0.048 ms)
///   exactly 0  → "0 {unit}"
fn fmt_val(value: f64, unit: &str) -> String {
    if value == 0.0 {
        format!("0 {unit}")
    } else if value.abs() >= 10_000.0 {
        format!("{value:.1} {unit}")
    } else if value.abs() >= 1.0 {
        format!("{value:.2} {unit}")
    } else {
        format!("{value:.3} {unit}")
    }
}

fn fmt_pct(value: f64) -> String {
    if value.abs() >= 100.0 {
        format!("{value:.0}%")
    } else if value.abs() >= 10.0 {
        format!("{value:.1}%")
    } else {
        format!("{value:.2}%")
    }
}

/// Drop the last `cooldown` samples from a Vec, in place. Returns the number
/// dropped (clamped so we never drop more than the Vec contains).
fn trim_cooldown(values: &mut Vec<f64>, cooldown: usize) -> usize {
    let dropped = cooldown.min(values.len());
    values.truncate(values.len() - dropped);
    dropped
}

fn format_wall_clock(t: SystemTime) -> String {
    // Format as RFC3339-ish with millisecond precision. `chrono` is not a
    // dependency here, so we hand-format from UNIX-epoch components.
    let duration = match t.duration_since(UNIX_EPOCH) {
        Ok(d) => d,
        Err(_) => return "<before epoch>".to_string(),
    };
    let secs = duration.as_secs() as i64;
    let millis = duration.subsec_millis();

    // Convert to UTC calendar components (no leap-second support; fine for stats headers).
    let days = secs.div_euclid(86_400);
    let time_of_day = secs.rem_euclid(86_400);
    let hour = (time_of_day / 3600) as u32;
    let minute = ((time_of_day % 3600) / 60) as u32;
    let second = (time_of_day % 60) as u32;

    // Civil-from-days algorithm by Howard Hinnant (public domain).
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as i64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if m <= 2 { y + 1 } else { y };
    format!(
        "{year:04}-{m:02}-{d:02}T{hour:02}:{minute:02}:{second:02}.{millis:03}Z"
    )
}

// ── Gatherer spawn ───────────────────────────────────────────────────────────

/// Spawn the gatherer thread.
pub fn spawn_gatherer(
    frame_receivers: Vec<(String, Receiver<FramePacket>)>,
    multi_frame_sender: Sender<MultiFramePayload>,
    update_receiver: Receiver<super::types::GathererUpdate>,
    barrier: Arc<BreakableBarrier>,
    paused: Arc<AtomicBool>,
    performance_snapshot: Arc<std::sync::Mutex<Option<String>>>,
) -> JoinHandle<()> {
    thread::spawn(move || {
        let mut step: i64 = 0;
        let mut frame_receivers = frame_receivers;
        let mut skip_sync_remaining: u32 = 0;
        let mut camera_count = frame_receivers.len();

        // ── Per-camera stats buckets (outer index = camera position 0..N) ──
        // Note: there is NO per-camera barrier-wait metric. The camera stamps
        // its barrier timestamps after sending its packet downstream, so any
        // per-camera barrier-wait carried in the packet would belong to the
        // PREVIOUS iteration — an off-by-one bug that mixed iterations in
        // single-packet computations. See `camera/types.rs` for the full note.
        // The gatherer's OWN barrier wait is still measured (single-iteration
        // scope) below.
        let mut per_camera_wait_for_frame: Vec<Vec<f64>> = vec![Vec::new(); camera_count];
        let mut per_camera_jpeg_extract: Vec<Vec<f64>> = vec![Vec::new(); camera_count];
        let mut per_camera_channel_send_wait: Vec<Vec<f64>> = vec![Vec::new(); camera_count];
        let mut per_camera_cycle_total: Vec<Vec<f64>> = vec![Vec::new(); camera_count];
        let mut camera_labels: Vec<String> = vec!["?".to_string(); camera_count];
        // Real camera_index per gatherer-position, used to sort rows in the
        // printed tables. -1 means we haven't seen a frame from this position
        // yet (first frame's identity will populate it).
        let mut camera_indices: Vec<i32> = vec![-1; camera_count];

        // ── Multiframe-level stats (one sample per multiframe) ──
        let mut frame_arrival_spread_values: Vec<f64> = Vec::new();
        let mut thread_wakeup_spread_values: Vec<f64> = Vec::new();
        let mut multiframe_interval_ns: Vec<f64> = Vec::new();

        // ── Gatherer-loop stats (one sample per multiframe) ──
        let mut gatherer_frames_collection: Vec<f64> = Vec::new();
        let mut gatherer_barrier_wait_values: Vec<f64> = Vec::new();
        let mut gatherer_payload_assembly: Vec<f64> = Vec::new();
        let mut gatherer_downstream_send: Vec<f64> = Vec::new();

        // ── Cross-iteration carryover for cycle_total and FPS ──
        let mut prev_loop_starts: Vec<Option<i64>> = vec![None; camera_count];
        let mut prev_first_frame_avail_ns: Option<i64> = None;

        let mut gatherer_sm = GathererStateMachine::new();

        loop {
            // ── Drain any pending gatherer updates (add/remove cameras) ──
            while let Ok(update) = update_receiver.try_recv() {
                match update {
                    super::types::GathererUpdate::AddCamera {
                        camera_id,
                        frame_receiver,
                    } => {
                        tracing::info!(
                            "[gatherer] added camera '{}' at step {}",
                            camera_id, step
                        );
                        frame_receivers.push((camera_id, frame_receiver));
                        camera_count = frame_receivers.len();
                        skip_sync_remaining = 3; // skip a few cycles for lockstep catch-up
                        per_camera_wait_for_frame.push(Vec::new());
                        per_camera_jpeg_extract.push(Vec::new());
                        per_camera_channel_send_wait.push(Vec::new());
                        per_camera_cycle_total.push(Vec::new());
                        camera_labels.push("?".to_string());
                        camera_indices.push(-1);
                        prev_loop_starts.push(None);
                    }
                    super::types::GathererUpdate::RemoveCamera { camera_id } => {
                        tracing::debug!(
                            "[gatherer] removing camera '{}' at step {}",
                            camera_id, step
                        );
                        if let Some(pos) =
                            frame_receivers.iter().position(|(id, _)| *id == camera_id)
                        {
                            frame_receivers.remove(pos);
                            per_camera_wait_for_frame.remove(pos);
                            per_camera_jpeg_extract.remove(pos);
                            per_camera_channel_send_wait.remove(pos);
                            per_camera_cycle_total.remove(pos);
                            camera_labels.remove(pos);
                            camera_indices.remove(pos);
                            prev_loop_starts.remove(pos);
                        }
                        camera_count = frame_receivers.len();
                    }
                }
            }

            if camera_count == 0 {
                tracing::info!("[gatherer] no cameras left, exiting");
                break;
            }

            tracing::trace!(
                "[GATHER step {step}] CollectingFrames: waiting for {camera_count} camera(s)..."
            );
            // ── CollectingFrames: recv() one frame from each camera ──
            let mut frames: Vec<FramePacket> = Vec::with_capacity(camera_count);
            let mut disconnected = false;

            for (index, (camera_id, receiver)) in frame_receivers.iter().enumerate() {
                tracing::trace!(
                    "[GATHER step {step}] blocking recv() for camera[{index}] id={camera_id}..."
                );
                match receiver.recv() {
                    Ok(mut packet) => {
                        packet.timestamps.gatherer_received_ns =
                            performance_counter_nanoseconds();
                        tracing::trace!(
                            "[GATHER step {step}] RECV camera[{index}] id={camera_id} \
                             frame#{}  {:.1} KB  gatherer_recv_ns={}",
                            packet.frame_number,
                            packet.data.len() as f64 / 1024.0,
                            packet.timestamps.gatherer_received_ns,
                        );
                        frames.push(packet);
                    }
                    Err(_) => {
                        tracing::info!(
                            "[gatherer] camera '{}' (index {}) disconnected at step {} — shutting down",
                            camera_id, index, step
                        );
                        disconnected = true;
                        break;
                    }
                }
            }

            if disconnected {
                barrier.break_barrier();
                break;
            }

            // ── Validate: ALL cameras must be on the same frame number ──
            if camera_count > 1 && skip_sync_remaining == 0 {
                let first_fn = frames[0].frame_number;
                for (i, frame) in frames.iter().enumerate().skip(1) {
                    if frame.frame_number != first_fn {
                        panic!(
                            "CAMERA SYNC LOST at step {step}: camera[0] frame#={first_fn}, \
                             camera[{i}] frame#={} — cameras are out of sync!",
                            frame.frame_number
                        );
                    }
                }
                tracing::trace!(
                    "[GATHER step {step}] frame numbers OK: all cameras at frame#{first_fn}"
                );
            }
            if skip_sync_remaining > 0 {
                skip_sync_remaining -= 1;
            }

            // ── Snapshot camera labels + indices (cheap; only runs while "?") ──
            for (i, frame) in frames.iter().enumerate() {
                if camera_labels[i] == "?" {
                    camera_labels[i] = frame.identity.label();
                    camera_indices[i] = frame.identity.camera_index;
                }
            }

            // ── AllFramesReceived ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::AllFramesReceived) {
                tracing::error!("[gatherer] invalid state transition: {e}");
            }

            // ── WaitingAtBarrier → hit the barrier — release all cameras ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::WaitingAtBarrier) {
                tracing::error!("[gatherer] invalid state transition: {e}");
            }
            if !barrier.wait() {
                tracing::warn!("[gatherer] barrier broken, shutting down");
                break;
            }

            // ── AssemblingPayload ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::AssemblingPayload) {
                tracing::error!("[gatherer] invalid state transition: {e}");
            }

            // ── Assemble payload ──
            let mut payload = MultiFramePayload {
                frames,
                frame_number: step,
                all_frames_received_ns: gatherer_sm.timestamps.all_frames_received_ns,
                payload_assembled_ns: 0,
                pre_send_downstream_ns: 0,
            };

            // ── AssemblingPayload → SendingDownstream ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::SendingDownstream) {
                tracing::error!("[gatherer] invalid state transition: {e}");
            }
            payload.payload_assembled_ns = gatherer_sm.timestamps.payload_assembled_ns;
            payload.pre_send_downstream_ns = gatherer_sm.timestamps.pre_send_downstream_ns;

            // ── Push statistics for this multiframe (warmup-gated) ──
            let push_stats = step >= STATS_WARMUP_MULTIFRAMES;

            if push_stats {
                // Per-camera per-frame
                for (i, frame) in payload.frames.iter().enumerate() {
                    let ts = &frame.timestamps;
                    if ts.loop_start_ns > 0
                        && ts.frame_available_ns >= ts.loop_start_ns
                    {
                        per_camera_wait_for_frame[i]
                            .push((ts.frame_available_ns - ts.loop_start_ns) as f64);
                    }
                    if ts.frame_available_ns > 0
                        && ts.post_jpeg_extract_ns >= ts.frame_available_ns
                    {
                        per_camera_jpeg_extract[i].push(
                            (ts.post_jpeg_extract_ns - ts.frame_available_ns) as f64,
                        );
                    }
                    if ts.pre_send_ns > 0
                        && ts.gatherer_received_ns >= ts.pre_send_ns
                    {
                        per_camera_channel_send_wait[i].push(
                            (ts.gatherer_received_ns - ts.pre_send_ns) as f64,
                        );
                    }
                    if let Some(prev) = prev_loop_starts[i] {
                        if ts.loop_start_ns > prev {
                            per_camera_cycle_total[i]
                                .push((ts.loop_start_ns - prev) as f64);
                        }
                    }
                }

                // Multiframe-level
                frame_arrival_spread_values.push(payload.frame_arrival_spread_ns() as f64);
                thread_wakeup_spread_values.push(payload.thread_wakeup_spread_ns() as f64);
                if let Some(prev_ts) = prev_first_frame_avail_ns {
                    let first = payload
                        .frames
                        .first()
                        .map(|f| f.timestamps.frame_available_ns)
                        .unwrap_or(0);
                    if first > prev_ts {
                        multiframe_interval_ns.push((first - prev_ts) as f64);
                    }
                }

                // Gatherer-loop
                let collecting_start = gatherer_sm.timestamps.collecting_start_ns;
                let all_recv = gatherer_sm.timestamps.all_frames_received_ns;
                let gather_post_bar = gatherer_sm.timestamps.post_barrier_ns;
                let payload_assembled = gatherer_sm.timestamps.payload_assembled_ns;
                if collecting_start > 0 && all_recv >= collecting_start {
                    gatherer_frames_collection.push((all_recv - collecting_start) as f64);
                }
                if all_recv > 0 && gather_post_bar >= all_recv {
                    gatherer_barrier_wait_values.push((gather_post_bar - all_recv) as f64);
                }
                if gather_post_bar > 0 && payload_assembled >= gather_post_bar {
                    gatherer_payload_assembly
                        .push((payload_assembled - gather_post_bar) as f64);
                }
            }

            // ── Ring-buffer cap: prevent unbounded memory growth ──
            if push_stats {
                truncate_ring_buffer(&mut per_camera_wait_for_frame);
                truncate_ring_buffer(&mut per_camera_jpeg_extract);
                truncate_ring_buffer(&mut per_camera_channel_send_wait);
                truncate_ring_buffer(&mut per_camera_cycle_total);
                truncate_ring(&mut frame_arrival_spread_values);
                truncate_ring(&mut thread_wakeup_spread_values);
                truncate_ring(&mut multiframe_interval_ns);
                truncate_ring(&mut gatherer_frames_collection);
                truncate_ring(&mut gatherer_barrier_wait_values);
                truncate_ring(&mut gatherer_payload_assembly);
                truncate_ring(&mut gatherer_downstream_send);

                // Update performance snapshot every ~3s (every 100 multiframes)
                if step % 100 == 0 {
                    if let Ok(mut slot) = performance_snapshot.lock() {
                        *slot = Some(build_snapshot_json(
                            &per_camera_wait_for_frame,
                            &per_camera_jpeg_extract,
                            &per_camera_channel_send_wait,
                            &per_camera_cycle_total,
                            &frame_arrival_spread_values,
                            &multiframe_interval_ns,
                            &camera_labels,
                        ));
                    }
                }
            }

            // ── Update cross-iteration carryover (always, regardless of warmup) ──
            for (i, frame) in payload.frames.iter().enumerate() {
                prev_loop_starts[i] = Some(frame.timestamps.loop_start_ns);
            }
            prev_first_frame_avail_ns = payload
                .frames
                .first()
                .map(|f| f.timestamps.frame_available_ns);

            step += 1;

            tracing::trace!(
                "[GATHER step {step}] sending payload with {} frames downstream...",
                payload.frames.len(),
            );

            // ── Send downstream — capture post-send time for downstream_send stat ──
            let pre_send_downstream = gatherer_sm.timestamps.pre_send_downstream_ns;
            if multi_frame_sender.send(payload).is_err() {
                tracing::warn!("[gatherer] downstream disconnected, shutting down");
                barrier.break_barrier();
                break;
            }
            if push_stats {
                let post_send_downstream_ns = performance_counter_nanoseconds();
                if pre_send_downstream > 0
                    && post_send_downstream_ns >= pre_send_downstream
                {
                    gatherer_downstream_send
                        .push((post_send_downstream_ns - pre_send_downstream) as f64);
                }
            }
            tracing::trace!("[GATHER step {step}] payload sent downstream OK");

            // ── SendingDownstream → CollectingFrames ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::CollectingFrames) {
                tracing::error!("[gatherer] invalid state transition: {e}");
            }

            // ── Paused spin ────────────────────────────────────────────
            // Placed AFTER the full cycle (recv → barrier → assemble → send
            // downstream) so the gatherer has completed its work for this
            // iteration before spinning. Drains AddCamera/RemoveCamera updates
            // while paused so camera set changes are applied promptly.
            while paused.load(Ordering::SeqCst) {
                while let Ok(update) = update_receiver.try_recv() {
                    match update {
                        super::types::GathererUpdate::AddCamera {
                            camera_id,
                            frame_receiver,
                        } => {
                            tracing::info!(
                                "[gatherer] added camera '{}' at step {} (while paused)",
                                camera_id, step
                            );
                            frame_receivers.push((camera_id, frame_receiver));
                            camera_count = frame_receivers.len();
                            skip_sync_remaining = 3;
                            per_camera_wait_for_frame.push(Vec::new());
                            per_camera_jpeg_extract.push(Vec::new());
                            per_camera_channel_send_wait.push(Vec::new());
                            per_camera_cycle_total.push(Vec::new());
                            camera_labels.push("?".to_string());
                            camera_indices.push(-1);
                            prev_loop_starts.push(None);
                        }
                        super::types::GathererUpdate::RemoveCamera { camera_id } => {
                            tracing::debug!(
                                "[gatherer] removing camera '{}' (while paused)",
                                camera_id
                            );
                            if let Some(pos) =
                                frame_receivers.iter().position(|(id, _)| *id == camera_id)
                            {
                                frame_receivers.remove(pos);
                                per_camera_wait_for_frame.remove(pos);
                                per_camera_jpeg_extract.remove(pos);
                                per_camera_channel_send_wait.remove(pos);
                                per_camera_cycle_total.remove(pos);
                                camera_labels.remove(pos);
                                camera_indices.remove(pos);
                                prev_loop_starts.remove(pos);
                            }
                            camera_count = frame_receivers.len();
                        }
                    }
                }
                if camera_count == 0 {
                    tracing::info!("[gatherer] no cameras left (while paused), exiting");
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(1));
            }
            if camera_count == 0 {
                break;
            }
            // ── End paused spin ────────────────────────────────────────
        }

        // ── Apply cooldown trim (drop last N samples from every Vec) ──
        for vec in per_camera_wait_for_frame.iter_mut() {
            trim_cooldown(vec, STATS_COOLDOWN_MULTIFRAMES);
        }
        for vec in per_camera_jpeg_extract.iter_mut() {
            trim_cooldown(vec, STATS_COOLDOWN_MULTIFRAMES);
        }
        for vec in per_camera_channel_send_wait.iter_mut() {
            trim_cooldown(vec, STATS_COOLDOWN_MULTIFRAMES);
        }
        for vec in per_camera_cycle_total.iter_mut() {
            trim_cooldown(vec, STATS_COOLDOWN_MULTIFRAMES);
        }
        trim_cooldown(&mut frame_arrival_spread_values, STATS_COOLDOWN_MULTIFRAMES);
        trim_cooldown(&mut thread_wakeup_spread_values, STATS_COOLDOWN_MULTIFRAMES);
        trim_cooldown(&mut multiframe_interval_ns, STATS_COOLDOWN_MULTIFRAMES);
        trim_cooldown(&mut gatherer_frames_collection, STATS_COOLDOWN_MULTIFRAMES);
        trim_cooldown(&mut gatherer_barrier_wait_values, STATS_COOLDOWN_MULTIFRAMES);
        trim_cooldown(&mut gatherer_payload_assembly, STATS_COOLDOWN_MULTIFRAMES);
        trim_cooldown(&mut gatherer_downstream_send, STATS_COOLDOWN_MULTIFRAMES);

        // ── Print statistics on exit ──
        print_statistics(
            step,
            camera_count,
            &camera_labels,
            &camera_indices,
            &per_camera_wait_for_frame,
            &per_camera_jpeg_extract,
            &per_camera_channel_send_wait,
            &per_camera_cycle_total,
            &frame_arrival_spread_values,
            &thread_wakeup_spread_values,
            &multiframe_interval_ns,
            &gatherer_frames_collection,
            &gatherer_barrier_wait_values,
            &gatherer_payload_assembly,
            &gatherer_downstream_send,
        );

        tracing::info!("[gatherer] exited after {step} steps");
    })
}

// ── Statistics printing ──────────────────────────────────────────────────────

fn line(s: &str) {
    tracing::info!("{}", s);
}

// ── Table-printing primitives ────────────────────────────────────────────────

/// A simple table schema: one left-aligned name column plus one or more
/// right-aligned data cells. Used to print compact tables of statistics where
/// every row shares the same column layout.
struct TableSchema {
    name_w: usize,
    cell_widths: Vec<usize>,
}

impl TableSchema {
    fn print_header(&self, name_label: &str, headers: &[&str]) {
        let mut s = String::from("  ");
        s.push_str(&format!("{name_label:<w$}", w = self.name_w));
        for (h, w) in headers.iter().zip(&self.cell_widths) {
            s.push_str(" │ ");
            s.push_str(&format!("{h:>cw$}", cw = *w));
        }
        line(&s);
    }

    fn print_separator(&self) {
        let mut s = String::from("  ");
        s.push_str(&"─".repeat(self.name_w));
        for w in &self.cell_widths {
            s.push_str("─┼─");
            s.push_str(&"─".repeat(*w));
        }
        line(&s);
    }

    fn print_row(&self, name: &str, cells: &[String]) {
        let mut s = String::from("  ");
        s.push_str(&format!("{name:<w$}", w = self.name_w));
        for (cell, w) in cells.iter().zip(&self.cell_widths) {
            s.push_str(" │ ");
            s.push_str(&format!("{cell:>cw$}", cw = *w));
        }
        line(&s);
    }
}

/// Format a row of stats cells for the "summary table" schema (median, mean,
/// std, CV%, min, max, n). Returns the Vec of formatted strings ready to be
/// passed to `TableSchema::print_row`.
fn summary_cells(stats: &Stats, div: f64, unit: &str) -> Vec<String> {
    vec![
        fmt_val(stats.median / div, unit),
        fmt_val(stats.mean / div, unit),
        fmt_val(stats.std / div, unit),
        fmt_pct(stats.cv_pct),
        fmt_val(stats.min / div, unit),
        fmt_val(stats.max / div, unit),
        stats.n.to_string(),
    ]
}

/// Format a row of stats cells for the "per-camera table" schema (median,
/// mean, std, CV%, % of cycle, n).
fn per_camera_cells(
    stats: &Stats,
    div: f64,
    unit: &str,
    pct_of_cycle: Option<f64>,
) -> Vec<String> {
    vec![
        fmt_val(stats.median / div, unit),
        fmt_val(stats.mean / div, unit),
        fmt_val(stats.std / div, unit),
        fmt_pct(stats.cv_pct),
        pct_of_cycle.map(fmt_pct).unwrap_or_else(|| "—".to_string()),
        stats.n.to_string(),
    ]
}

/// Print one per-metric per-camera table block (header → data rows →
/// Mean/Median camera summary rows → across-cameras spread line). Rows are
/// printed in the order given by `sort_order` (sorted by `camera_index`).
///
/// Summary rows:
///   "Mean camera"   — for each column, the MEAN of the N per-camera values.
///   "Median camera" — for each column, the MEDIAN of the N per-camera values.
///
/// Does NOT print the metric's prose description — see
/// `FRAMERATE_METRIC_DEFINITIONS.md` at the crate root for that.
fn print_per_camera_table(
    metric_name: &str,
    formula: &str,
    schema: &TableSchema,
    per_camera_values: &[Vec<f64>],
    per_camera_cycle_total: &[Vec<f64>],
    camera_labels: &[String],
    sort_order: &[usize],
) {
    line(&format!("  {metric_name}  {formula}"));
    let all_values: Vec<f64> = per_camera_values
        .iter()
        .flat_map(|v| v.iter().copied())
        .collect();
    if all_values.is_empty() {
        line("    (insufficient samples)");
        line("");
        return;
    }
    let (div, unit) = auto_scale(&all_values);

    schema.print_header(
        "Camera",
        &["Median", "Mean", "Std", "CV%", "% cycle", "n"],
    );
    schema.print_separator();

    // Accumulators for cross-camera summary rows.
    let mut acc_medians: Vec<f64> = Vec::new();
    let mut acc_means: Vec<f64> = Vec::new();
    let mut acc_stds: Vec<f64> = Vec::new();
    let mut acc_cv_pcts: Vec<f64> = Vec::new();
    let mut acc_pct_of_cycles: Vec<f64> = Vec::new();

    for &i in sort_order {
        let values = match per_camera_values.get(i) {
            Some(v) => v,
            None => continue,
        };
        let label = camera_labels.get(i).cloned().unwrap_or_default();
        let stats = match compute_stats(values) {
            Some(s) => s,
            None => {
                schema.print_row(&label, &["(no samples)".to_string()]);
                continue;
            }
        };
        let pct_of_cycle = per_camera_cycle_total
            .get(i)
            .and_then(|c| compute_stats(c))
            .map(|cs| {
                if cs.median > 0.0 {
                    (stats.median / cs.median) * 100.0
                } else {
                    0.0
                }
            });

        acc_medians.push(stats.median);
        acc_means.push(stats.mean);
        acc_stds.push(stats.std);
        acc_cv_pcts.push(stats.cv_pct);
        if let Some(pct) = pct_of_cycle {
            acc_pct_of_cycles.push(pct);
        }

        schema.print_row(&label, &per_camera_cells(&stats, div, unit, pct_of_cycle));
    }

    if acc_medians.len() >= 2 {
        // Compute cross-camera stats for each column.
        let s_med = compute_stats(&acc_medians);
        let s_mean = compute_stats(&acc_means);
        let s_std = compute_stats(&acc_stds);
        let s_cv = compute_stats(&acc_cv_pcts);
        let s_pct = if acc_pct_of_cycles.is_empty() {
            None
        } else {
            compute_stats(&acc_pct_of_cycles)
        };

        let pct_cell = |opt: &Option<Stats>, f: fn(&Stats) -> f64| -> String {
            opt.as_ref().map_or("—".to_string(), |s| fmt_pct(f(s)))
        };
        let val_cell = |opt: &Option<Stats>, f: fn(&Stats) -> f64| -> String {
            opt.as_ref()
                .map_or("—".to_string(), |s| fmt_val(f(s) / div, unit))
        };

        schema.print_separator();

        // Mean camera — each column is the mean of the N per-camera values.
        schema.print_row(
            "Mean camera",
            &[
                val_cell(&s_med, |s| s.mean),
                val_cell(&s_mean, |s| s.mean),
                val_cell(&s_std, |s| s.mean),
                pct_cell(&s_cv, |s| s.mean),
                pct_cell(&s_pct, |s| s.mean),
                "—".to_string(),
            ],
        );

        // Median camera — each column is the median of the N per-camera values.
        schema.print_row(
            "Median camera",
            &[
                val_cell(&s_med, |s| s.median),
                val_cell(&s_mean, |s| s.median),
                val_cell(&s_std, |s| s.median),
                pct_cell(&s_cv, |s| s.median),
                pct_cell(&s_pct, |s| s.median),
                "—".to_string(),
            ],
        );

        // Across-cameras spread line (max−min of per-camera medians).
        let spread = acc_medians.iter().cloned().fold(f64::MIN, f64::max)
            - acc_medians.iter().cloned().fold(f64::MAX, f64::min);
        let across_cv = s_med.as_ref().map_or(0.0, |s| s.cv_pct);
        schema.print_separator();
        line(&format!(
            "  Across cameras (of {n} per-camera medians):  spread {sp}  │  CV% {cv}",
            n = acc_medians.len(),
            sp = fmt_val(spread / div, unit),
            cv = fmt_pct(across_cv),
        ));
    }
    line("");
}


#[allow(clippy::too_many_arguments)]
fn print_statistics(
    step: i64,
    camera_count: usize,
    camera_labels: &[String],
    camera_indices: &[i32],
    per_camera_wait_for_frame: &[Vec<f64>],
    per_camera_jpeg_extract: &[Vec<f64>],
    per_camera_channel_send_wait: &[Vec<f64>],
    per_camera_cycle_total: &[Vec<f64>],
    frame_arrival_spread_values: &[f64],
    thread_wakeup_spread_values: &[f64],
    multiframe_interval_ns: &[f64],
    gatherer_frames_collection: &[f64],
    gatherer_barrier_wait_values: &[f64],
    gatherer_payload_assembly: &[f64],
    gatherer_downstream_send: &[f64],
) {
    let multiframe_fps: Vec<f64> = multiframe_interval_ns
        .iter()
        .filter(|dt| **dt > 0.0)
        .map(|dt_ns| 1_000_000_000.0 / dt_ns)
        .collect();

    let retained = multiframe_interval_ns.len();
    let total_observed = step as usize;
    let excluded_warmup = STATS_WARMUP_MULTIFRAMES.min(step) as usize;
    let excluded_cooldown = STATS_COOLDOWN_MULTIFRAMES.min(total_observed);
    let total_per_camera_samples: usize =
        per_camera_wait_for_frame.iter().map(|v| v.len()).sum();

    // Sort cameras by their real camera_index (not by the gatherer-internal
    // receive order, which is determined by HashMap iteration order). Cameras
    // we never saw a frame from (index == -1) sort to the end.
    let mut sort_order: Vec<usize> = (0..camera_count).collect();
    sort_order.sort_by_key(|&i| {
        let idx = camera_indices.get(i).copied().unwrap_or(i32::MAX);
        if idx < 0 { i32::MAX } else { idx }
    });

    // Shared schemas used by all tables in the block. Two flavors:
    //   - summary: one row per metric, columns = median/mean/std/CV%/min/max/n
    //   - per_camera: one row per camera, columns = median/mean/std/CV%/% cycle/n
    let summary_schema = TableSchema {
        name_w: 24,
        cell_widths: vec![10, 10, 10, 6, 10, 10, 4],
    };
    let summary_headers = ["Median", "Mean", "Std", "CV%", "Min", "Max", "n"];
    let per_camera_schema = TableSchema {
        name_w: 26,
        cell_widths: vec![10, 10, 10, 6, 8, 4],
    };

    // ── HEADER ──
    line("");
    line("═══════════════════════════════════════════════════════════════════════════════");
    line("  GATHERER STATISTICS");
    line(&format!(
        "  {camera_count} camera{cs}, {step} multiframe{ms} observed",
        cs = if camera_count == 1 { "" } else { "s" },
        ms = if step == 1 { "" } else { "s" },
    ));
    match anchor_wall_clock_time() {
        Some(t) => line(&format!(
            "  T=0 anchored at {} (system wall-clock)",
            format_wall_clock(t)
        )),
        None => line("  T=0 anchored at <unknown — init_logging() was never called>"),
    };
    line("  All timestamps below are nanoseconds since that anchor.");
    line(&format!(
        "  Samples retained: {} multiframes  (warmup excluded: {}; cooldown excluded: {})",
        retained, excluded_warmup, excluded_cooldown
    ));
    line("───────────────────────────────────────────────────────────────────────────────");
    line("");

    // ── 1. THROUGHPUT ──
    // Two rows: rate (fps) and period (ms). Same throughput information
    // expressed two ways so it's easy to compare with the duration-valued
    // metrics in the other tables.
    line("▸ THROUGHPUT ────────────────────────────────────────────────────────────────");
    line("");
    summary_schema.print_header("Metric", &summary_headers);
    summary_schema.print_separator();
    if let Some(stats) = compute_stats(&multiframe_fps) {
        summary_schema.print_row("Multiframe FPS", &summary_cells(&stats, 1.0, "fps"));
    } else {
        summary_schema.print_row("Multiframe FPS", &["(insufficient samples)".to_string()]);
    }
    if let Some(stats) = compute_stats(multiframe_interval_ns) {
        let (div, unit) = auto_scale(multiframe_interval_ns);
        summary_schema.print_row("Multiframe duration", &summary_cells(&stats, div, unit));
    } else {
        summary_schema.print_row(
            "Multiframe duration",
            &["(insufficient samples)".to_string()],
        );
    }
    line("");

    // ── 2. INTRA-MULTIFRAME ALIGNMENT ──
    line("▸ INTRA-MULTIFRAME ALIGNMENT  (one sample per multiframe) ───────────────────");
    line("");
    summary_schema.print_header("Metric", &summary_headers);
    summary_schema.print_separator();
    if let Some(stats) = compute_stats(frame_arrival_spread_values) {
        let (div, unit) = auto_scale(frame_arrival_spread_values);
        summary_schema.print_row("Frame arrival spread", &summary_cells(&stats, div, unit));
    }
    if let Some(stats) = compute_stats(thread_wakeup_spread_values) {
        let (div, unit) = auto_scale(thread_wakeup_spread_values);
        summary_schema.print_row("Thread wakeup spread", &summary_cells(&stats, div, unit));
    }
    line("");

    // ── 3. PER-CAMERA LIFECYCLE ──
    line(&format!(
        "▸ PER-CAMERA LIFECYCLE  (one sample per camera per multiframe; {} total) ────",
        total_per_camera_samples
    ));
    line("  One table per metric. Each table: per-camera rows (ordered by");
    line("  camera_index) + an across-cameras summary row computed over the");
    line("  per-camera medians.");
    line("");
    print_per_camera_table(
        "WAIT FOR FRAME",
        "(frame_available_ns − loop_start_ns)",
        &per_camera_schema,
        per_camera_wait_for_frame,
        per_camera_cycle_total,
        camera_labels,
        &sort_order,
    );
    print_per_camera_table(
        "JPEG EXTRACT",
        "(post_jpeg_extract_ns − frame_available_ns)",
        &per_camera_schema,
        per_camera_jpeg_extract,
        per_camera_cycle_total,
        camera_labels,
        &sort_order,
    );
    print_per_camera_table(
        "CHANNEL SEND WAIT",
        "(gatherer_received_ns − pre_send_ns)",
        &per_camera_schema,
        per_camera_channel_send_wait,
        per_camera_cycle_total,
        camera_labels,
        &sort_order,
    );
    print_per_camera_table(
        "CYCLE TOTAL",
        "(loop_start_{N+1} − loop_start_N, per camera)",
        &per_camera_schema,
        per_camera_cycle_total,
        per_camera_cycle_total,
        camera_labels,
        &sort_order,
    );

    // ── 4. GATHERER LOOP ──
    line(&format!(
        "▸ GATHERER LOOP  (one sample per multiframe; {} samples) ────────────────────",
        gatherer_frames_collection.len()
    ));
    line("");
    summary_schema.print_header("Metric", &summary_headers);
    summary_schema.print_separator();
    let gatherer_rows: [(&str, &[f64]); 4] = [
        ("Frames collection time", gatherer_frames_collection),
        ("Gatherer barrier wait", gatherer_barrier_wait_values),
        ("Payload assembly", gatherer_payload_assembly),
        ("Downstream send", gatherer_downstream_send),
    ];
    for (name, values) in &gatherer_rows {
        if let Some(stats) = compute_stats(values) {
            let (div, unit) = auto_scale(values);
            summary_schema.print_row(name, &summary_cells(&stats, div, unit));
        } else {
            summary_schema.print_row(name, &["(insufficient samples)".to_string()]);
        }
    }
    line("");

    // ── 5. DEFINITIONS POINTER ──
    line("▸ DEFINITIONS & METHODOLOGY ─────────────────────────────────────────────────");
    line("");
    let definitions_path =
        concat!(env!("CARGO_MANIFEST_DIR"), "/FRAMERATE_METRIC_DEFINITIONS.md");
    line(&format!(
        "  See {definitions_path} for definitions of every metric"
    ));
    line("  above, the timestamp formulas behind them, and the methodology notes");
    line("  (warmup/cooldown rationale, CV%, % of cycle semantics, etc.).");
    line("");
    line("═══════════════════════════════════════════════════════════════════════════════");
    line("");
}

// ── Performance snapshot (lightweight JSON for PyO3 bridge polling) ─────

fn build_snapshot_json(
    per_camera_wait_for_frame: &[Vec<f64>],
    per_camera_jpeg_extract: &[Vec<f64>],
    per_camera_channel_send_wait: &[Vec<f64>],
    per_camera_cycle_total: &[Vec<f64>],
    frame_arrival_spread: &[f64],
    multiframe_interval_ns: &[f64],
    camera_labels: &[String],
) -> String {
    let fps: Vec<f64> = multiframe_interval_ns
        .iter()
        .filter(|dt| **dt > 0.0)
        .map(|dt_ns| 1_000_000_000.0 / dt_ns)
        .collect();

    let fps_stats = compute_stats(&fps);
    let spread_stats = compute_stats(frame_arrival_spread);

    let per_camera: Vec<serde_json::Value> = camera_labels
        .iter()
        .enumerate()
        .map(|(i, label)| {
            let wf = per_camera_wait_for_frame.get(i).map(|v| stat_to_json(compute_stats(v)));
            let je = per_camera_jpeg_extract.get(i).map(|v| stat_to_json(compute_stats(v)));
            let cs = per_camera_channel_send_wait.get(i).map(|v| stat_to_json(compute_stats(v)));
            let ct = per_camera_cycle_total.get(i).map(|v| stat_to_json(compute_stats(v)));
            serde_json::json!({
                "camera_label": label,
                "wait_for_frame_us": wf,
                "jpeg_extract_us": je,
                "channel_send_wait_us": cs,
                "cycle_total_ms": ct,
            })
        })
        .collect();

    let snapshot = serde_json::json!({
        "multiframe_fps": stat_to_json(fps_stats),
        "frame_arrival_spread_us": stat_to_json(
            spread_stats.map(|mut s| {
                s.mean /= 1_000.0; s.median /= 1_000.0;
                s.std /= 1_000.0; s.min /= 1_000.0; s.max /= 1_000.0;
                s
            })
        ),
        "sample_count": multiframe_interval_ns.len(),
        "per_camera": per_camera,
    });

    snapshot.to_string()
}

fn stat_to_json(stats: Option<Stats>) -> serde_json::Value {
    match stats {
        Some(s) => serde_json::json!({
            "median_us": s.median / 1_000.0,
            "mean_us": s.mean / 1_000.0,
            "std_us": s.std / 1_000.0,
            "cv_pct": s.cv_pct,
            "min_us": s.min / 1_000.0,
            "max_us": s.max / 1_000.0,
            "n": s.n,
        }),
        None => serde_json::Value::Null,
    }
}
