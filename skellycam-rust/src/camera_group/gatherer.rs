use std::sync::mpsc::{Receiver, SyncSender};
use std::sync::Arc;
use std::thread::{self, JoinHandle};

use crate::camera::{CameraEvent, CameraHandle, FramePacket, MultiFramePayload};
use crate::camera_group::sync_utils::BreakableBarrier;

use super::state_machine::{GathererState, GathererStateMachine};

/// Computed summary statistics for a set of values.
struct Stats {
    median: f64,
    mean: f64,
    std: f64,
    min: f64,
    max: f64,
}

fn compute_stats(values: &[f64]) -> Stats {
    let n = values.len();
    let mut sorted: Vec<f64> = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let mean = values.iter().sum::<f64>() / n as f64;
    let median = sorted[n / 2];
    let min = sorted[0];
    let max = sorted[n - 1];
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
    let std = variance.sqrt();

    Stats { median, mean, std, min, max }
}

/// Pick the most human-readable unit for a set of nanosecond values.
/// Returns (divisor, unit_label). Median > 1ms → ms, > 1µs → µs, else ns.
fn auto_scale(values_ns: &[f64]) -> (f64, &'static str) {
    let stats = compute_stats(values_ns);
    if stats.median >= 1_000_000.0 {
        (1_000_000.0, "ms")
    } else if stats.median >= 1_000.0 {
        (1_000.0, "µs")
    } else {
        (1.0, "ns")
    }
}

/// Format a single value with its unit. Precision: 1 decimal, but if the
/// value rounds to 0.0, show 2 decimals so tiny values aren't hidden.
fn fmt_val(value: f64, unit: &str) -> String {
    if value == 0.0 {
        format!("0.0 {unit}")
    } else if value >= 10.0 {
        format!("{value:.1} {unit}")
    } else if value >= 1.0 {
        format!("{value:.2} {unit}")
    } else {
        format!("{value:.3} {unit}")
    }
}

fn fmt_pct(value: f64) -> String {
    if value >= 10.0 {
        format!("{value:.0}%")
    } else if value >= 1.0 {
        format!("{value:.1}%")
    } else {
        format!("{value:.2}%")
    }
}

/// Print a table row with aligned columns. Each column string already
/// includes any needed unit suffix.
fn print_table_row(cols: &[String], widths: &[usize]) {
    let line: String = cols
        .iter()
        .enumerate()
        .map(|(i, c)| {
            if i == 0 {
                // Left-align the label column
                format!("{:<width$}", c, width = widths[i])
            } else {
                // Right-align value columns
                format!("{:>width$}", c, width = widths[i])
            }
        })
        .collect::<Vec<_>>()
        .join("  ");
    eprintln!("  {line}");
}

fn print_separator(widths: &[usize]) {
    let total: usize = widths.iter().sum::<usize>() + (widths.len() - 1) * 2 + 2; // +2 for "  " prefix
    let sep = "─".repeat(total);
    eprintln!("  {sep}");
}

pub fn spawn_gatherer(
    frame_receivers: Vec<Receiver<FramePacket>>,
    event_receivers: Vec<Receiver<CameraEvent>>,
    camera_handles: Vec<CameraHandle>,
    multi_frame_sender: SyncSender<MultiFramePayload>,
    barrier: Arc<BreakableBarrier>,
) -> JoinHandle<()> {
    let camera_count = frame_receivers.len();

    thread::spawn(move || {
        let mut step: i64 = 0;
        let mut hardware_spread_values: Vec<f64> = Vec::new();
        let mut software_spread_values: Vec<f64> = Vec::new();
        let mut multiframe_interval_ns: Vec<f64> = Vec::new();
        let mut prev_multiframe_ts: Option<i64> = None;
        let mut duration_hardware_wait: Vec<f64> = Vec::new();
        let mut duration_barrier_sync: Vec<f64> = Vec::new();
        let mut duration_capture: Vec<f64> = Vec::new();
        let mut duration_channel_backpressure: Vec<f64> = Vec::new();
        let mut duration_total_iteration: Vec<f64> = Vec::new();

        let mut gatherer_sm = GathererStateMachine::new();

        loop {
            // ── Drain CameraEvent::Error reports from each camera. ──
            // This is camera-to-gatherer error reporting only — NOT command
            // processing. Top-level commands (pause/resume/recording, reconfigure,
            // shutdown) take other paths and do not flow through this drain.
            for event_receiver in &event_receivers {
                while let Ok(event) = event_receiver.try_recv() {
                    match event {
                        CameraEvent::Error(message) => {
                            eprintln!("[ERROR] {message}");
                        }
                    }
                }
            }

            // ── CollectingFrames: recv() one frame from each camera in sequence. ──
            // This is the primary synchronization point: the gatherer waits for
            // every camera to capture and send before continuing.
            let mut frames: Vec<FramePacket> = Vec::with_capacity(camera_count);
            let mut disconnected = false;

            for (index, receiver) in frame_receivers.iter().enumerate() {
                match receiver.recv() {
                    Ok(mut packet) => {
                        packet.timestamps.gatherer_received_ns =
                            crate::timestamps::performance::performance_counter_nanoseconds();
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
                barrier.break_barrier();
                break;
            }

            // ── CollectingFrames → AllFramesReceived (stamps all_frames_received_ns) ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::AllFramesReceived) {
                eprintln!("[gatherer] invalid gatherer state transition: {e}");
            }

            // ── AllFramesReceived → WaitingAtBarrier ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::WaitingAtBarrier) {
                eprintln!("[gatherer] invalid gatherer state transition: {e}");
            }

            // ── Hit the barrier IMMEDIATELY. ──
            // All cameras are at barrier.wait(); calling barrier.wait() here
            // releases them simultaneously. Cameras now spin for their next
            // hardware frame IN PARALLEL with the payload assembly and
            // downstream send that happen below.
            if !barrier.wait() {
                eprintln!("[gatherer] barrier broken, shutting down");
                for handle in &camera_handles {
                    handle.send_shutdown();
                }
                break;
            }

            // ── WaitingAtBarrier → AssemblingPayload (stamps post_barrier_ns) ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::AssemblingPayload) {
                eprintln!("[gatherer] invalid gatherer state transition: {e}");
            }

            let mut payload = MultiFramePayload {
                frames,
                frame_number: step,
                all_frames_received_ns: gatherer_sm.timestamps.all_frames_received_ns,
                payload_assembled_ns: 0,
                pre_send_downstream_ns: 0,
            };

            // ── AssemblingPayload → SendingDownstream (stamps payload_assembled_ns, pre_send_downstream_ns) ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::SendingDownstream) {
                eprintln!("[gatherer] invalid gatherer state transition: {e}");
            }
            payload.payload_assembled_ns = gatherer_sm.timestamps.payload_assembled_ns;
            payload.pre_send_downstream_ns = gatherer_sm.timestamps.pre_send_downstream_ns;

            // Track inter-multiframe interval
            if let Some(prev_ts) = prev_multiframe_ts {
                if step > 0 {
                    let first_frame_ts = payload.frames.first().map(|f| f.timestamps.frame_available_ns).unwrap_or(0);
                    multiframe_interval_ns.push((first_frame_ts - prev_ts) as f64);
                }
            }
            if let Some(first) = payload.frames.first() {
                prev_multiframe_ts = Some(first.timestamps.frame_available_ns);
            }

            // Track both hardware and software sync spreads
            let hardware_spread_ns = payload.hardware_sync_spread_ns() as f64;
            let software_spread_ns = payload.post_barrier_to_capture_spread_ns() as f64;
            hardware_spread_values.push(hardware_spread_ns);
            software_spread_values.push(software_spread_ns);

            // Track per-frame lifecycle timings for the shutdown statistics dump
            for frame in &payload.frames {
                let ts = &frame.timestamps;
                if ts.loop_start_ns > 0 && ts.frame_available_ns > 0 {
                    duration_hardware_wait.push((ts.frame_available_ns - ts.loop_start_ns) as f64);
                }
                if ts.pre_barrier_ns > 0 && ts.post_barrier_ns > 0 {
                    duration_barrier_sync.push((ts.post_barrier_ns - ts.pre_barrier_ns) as f64);
                }
                if ts.post_capture_ns > 0 && ts.pre_send_ns > 0 {
                    duration_capture.push((ts.pre_send_ns - ts.post_capture_ns) as f64);
                }
                if ts.pre_send_ns > 0 && ts.gatherer_received_ns > 0 {
                    duration_channel_backpressure.push((ts.gatherer_received_ns - ts.pre_send_ns) as f64);
                }
                if ts.loop_start_ns > 0 && ts.gatherer_received_ns > 0 {
                    duration_total_iteration.push((ts.gatherer_received_ns - ts.loop_start_ns) as f64);
                }
            }

            step += 1;

            if multi_frame_sender.send(payload).is_err() {
                eprintln!("[gatherer] downstream disconnected, shutting down");
                for handle in &camera_handles {
                    handle.send_shutdown();
                }
                barrier.break_barrier();
                break;
            }

            // ── SendingDownstream → CollectingFrames ──
            if let Err(e) = gatherer_sm.transition_to(GathererState::CollectingFrames) {
                eprintln!("[gatherer] invalid gatherer state transition: {e}");
            }
        }

        if step > 0 {
            let total_samples = duration_total_iteration.len();

            // ── Build FRAME TIMING table ──
            let mf_fps: Vec<f64> = multiframe_interval_ns.iter()
                .map(|dt_ns| 1_000_000_000.0 / dt_ns)
                .collect();
            let fps_stats = compute_stats(&mf_fps);

            let hw_spread_stats = compute_stats(&hardware_spread_values);
            let sw_spread_stats = compute_stats(&software_spread_values);

            let (hw_div, hw_unit) = auto_scale(&hardware_spread_values);
            let (sw_div, sw_unit) = auto_scale(&software_spread_values);

            let timing_headers = ["Metric", "Median", "Mean", "Std", "Min", "Max"]
                .iter().map(|s| s.to_string()).collect::<Vec<_>>();

            let timing_rows = [
                vec![
                    "multiframe fps".to_string(),
                    fmt_val(fps_stats.median, "fps"),
                    fmt_val(fps_stats.mean, "fps"),
                    fmt_val(fps_stats.std, "fps"),
                    fmt_val(fps_stats.min, "fps"),
                    fmt_val(fps_stats.max, "fps"),
                ],
                vec![
                    "hardware sync spread".to_string(),
                    fmt_val(hw_spread_stats.median / hw_div, hw_unit),
                    fmt_val(hw_spread_stats.mean / hw_div, hw_unit),
                    fmt_val(hw_spread_stats.std / hw_div, hw_unit),
                    fmt_val(hw_spread_stats.min / hw_div, hw_unit),
                    fmt_val(hw_spread_stats.max / hw_div, hw_unit),
                ],
                vec![
                    "software sync spread".to_string(),
                    fmt_val(sw_spread_stats.median / sw_div, sw_unit),
                    fmt_val(sw_spread_stats.mean / sw_div, sw_unit),
                    fmt_val(sw_spread_stats.std / sw_div, sw_unit),
                    fmt_val(sw_spread_stats.min / sw_div, sw_unit),
                    fmt_val(sw_spread_stats.max / sw_div, sw_unit),
                ],
            ];

            // ── Build PER-STAGE DURATIONS table ──
            let total_iteration_stats = compute_stats(&duration_total_iteration);

            let stages: [(&str, &[f64]); 5] = [
                ("hardware wait", &duration_hardware_wait),
                ("barrier sync", &duration_barrier_sync),
                ("capture memcpy", &duration_capture),
                ("channel backpressure", &duration_channel_backpressure),
                ("total iteration", &duration_total_iteration),
            ];

            // Pre-compute stats and units for each stage
            let stage_data: Vec<(&str, Stats, f64, &str, f64)> = stages.iter().map(|(name, values)| {
                let stats = compute_stats(values);
                let (div, unit) = auto_scale(values);
                let pct = if total_iteration_stats.median > 0.0 {
                    (stats.median / total_iteration_stats.median) * 100.0
                } else {
                    0.0
                };
                (*name, stats, div, unit, pct)
            }).collect();

            let duration_headers = ["Stage", "Median", "Mean", "Std", "Min", "Max", "% of total"]
                .iter().map(|s| s.to_string()).collect::<Vec<_>>();

            // ── Compute column widths (shared across both tables) ──
            let all_headers: [&[String]; 2] = [&timing_headers, &duration_headers];
            let all_rows: Vec<Vec<String>> = timing_rows.into_iter()
                .chain(stage_data.iter().map(|(name, stats, div, unit, pct)| {
                    vec![
                        name.to_string(),
                        fmt_val(stats.median / div, unit),
                        fmt_val(stats.mean / div, unit),
                        fmt_val(stats.std / div, unit),
                        fmt_val(stats.min / div, unit),
                        fmt_val(stats.max / div, unit),
                        fmt_pct(*pct),
                    ]
                }))
                .collect();

            let col_count = all_headers.iter().map(|h| h.len()).max().unwrap_or(0);
            let mut widths: Vec<usize> = vec![0; col_count];
            for h in &all_headers {
                for (i, s) in h.iter().enumerate() {
                    widths[i] = widths[i].max(s.len());
                }
            }
            for row in &all_rows {
                for (i, s) in row.iter().enumerate() {
                    if i < widths.len() {
                        widths[i] = widths[i].max(s.len());
                    }
                }
            }

            // ── Print tables ──
            eprintln!();
            eprintln!("══════════════════════════════════════════════════════════════════════");
            eprintln!(
                "  GATHERER STATISTICS — {step} multiframes, {camera_count} cameras, {total_samples} total samples"
            );
            eprintln!("──────────────────────────────────────────────────────────────────────");

            eprintln!();
            eprintln!("  FRAME TIMING");
            eprintln!("  ────────────");

            print_table_row(&timing_headers, &widths);
            print_separator(&widths);
            for row in &all_rows[..3] {
                print_table_row(row, &widths);
            }

            eprintln!();
            eprintln!("  PER-STAGE DURATIONS");
            eprintln!("  ───────────────────");

            print_table_row(&duration_headers, &widths);
            print_separator(&widths);
            for (i, row) in all_rows[3..].iter().enumerate() {
                if stage_data[i].0 == "total iteration" {
                    print_separator(&widths);
                }
                print_table_row(row, &widths);
            }

            eprintln!();
            eprintln!("  Spread legend: hardware = frame_available | software = post_barrier_to_capture");
            eprintln!("  % of total is each stage's median divided by total iteration median.");
            eprintln!("══════════════════════════════════════════════════════════════════════");
            eprintln!();
        }

        eprintln!("[gatherer] exited after {step} steps");
    })
}
