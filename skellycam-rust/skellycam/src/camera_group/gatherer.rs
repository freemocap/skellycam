use std::collections::HashMap;
use std::sync::mpsc::{Receiver, SyncSender};
use std::sync::Arc;
use std::thread::{self, JoinHandle};

use crate::camera::{CameraEvent, CameraHandle, FramePacket, MultiFramePayload};
use crate::sync_utils::BreakableBarrier;

/// Statistics tracked per camera across the entire run.
#[derive(Debug, Default)]
struct CameraStats {
    /// All inter-frame intervals in nanoseconds (for computing FPS distribution).
    intervals_ns: Vec<f64>,
    last_fps: f64,
}

/// Summary statistics computed over a set of values.
fn compute_summary(values: &[f64], label: &str, unit: &str) {
    if values.is_empty() {
        eprintln!("  {label}: no data");
        return;
    }
    let n = values.len();
    let mut sorted: Vec<f64> = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let mean = values.iter().sum::<f64>() / n as f64;
    let median = sorted[n / 2];
    let min = sorted[0];
    let max = sorted[n - 1];
    let q1 = sorted[n / 4];
    let q3 = sorted[3 * n / 4];
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
    let std = variance.sqrt();

    eprintln!("  ── {label} ({n} samples) ──");
    eprintln!("    mean={mean:.1}{unit}  median={median:.1}{unit}  std={std:.1}{unit}");
    eprintln!("    min={min:.1}{unit}  max={max:.1}{unit}");
    eprintln!("    Q1={q1:.1}{unit}  Q3={q3:.1}{unit}");
}

pub fn spawn_gatherer(
    frame_receivers: Vec<Receiver<FramePacket>>,
    event_receivers: Vec<Receiver<CameraEvent>>,
    camera_handles: Vec<CameraHandle>,
    multi_frame_sender: SyncSender<MultiFramePayload>,
    barrier: Arc<BreakableBarrier>,
) -> JoinHandle<()> {
    let camera_count = frame_receivers.len();
    let camera_labels: Vec<String> = camera_handles.iter()
        .map(|h| format!("{}:{}", h.identity.camera_index, h.identity.unique_identifier))
        .collect();

    thread::spawn(move || {
        let mut step: i64 = 0;
        let mut prev_timestamps: HashMap<String, i64> = HashMap::new();
        let mut per_camera_fps: HashMap<String, f64> = HashMap::new();
        let mut camera_stats: HashMap<String, CameraStats> = camera_labels.iter()
            .map(|label| (label.clone(), CameraStats::default()))
            .collect();
        let mut spread_values: Vec<f64> = Vec::new();
        let mut multiframe_interval_ns: Vec<f64> = Vec::new();
        let mut prev_multiframe_ts: Option<i64> = None;

        loop {
            // Synchronize with all cameras — all capture simultaneously
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

            // Collect frames (all captured at ~same instant)
            let mut frames: Vec<FramePacket> = Vec::with_capacity(camera_count);
            let mut disconnected = false;

            for (index, receiver) in frame_receivers.iter().enumerate() {
                match receiver.recv() {
                    Ok(packet) => frames.push(packet),
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

            let payload = MultiFramePayload { frames, step };

            // Track inter-multiframe interval
            if let Some(prev_ts) = prev_multiframe_ts {
                if step > 0 {
                    let first_frame_ts = payload.frames.first().map(|f| f.grab_timestamp_nanoseconds).unwrap_or(0);
                    multiframe_interval_ns.push((first_frame_ts - prev_ts) as f64);
                }
            }
            if let Some(first) = payload.frames.first() {
                prev_multiframe_ts = Some(first.grab_timestamp_nanoseconds);
            }

            // Track spread
            let spread_ns = payload.inter_camera_grab_spread_nanoseconds() as f64;
            spread_values.push(spread_ns);

            // Compute per-camera FPS and track intervals
            for frame in &payload.frames {
                let label = format!("{}:{}", frame.identity.camera_index, frame.identity.unique_identifier);
                if let Some(&prev_ts) = prev_timestamps.get(&label) {
                    let dt_ns = (frame.grab_timestamp_nanoseconds - prev_ts) as f64;
                    if dt_ns > 0.0 {
                        let fps = 1_000_000_000.0 / dt_ns;
                        per_camera_fps.insert(label.clone(), fps);
                        if let Some(stats) = camera_stats.get_mut(&label) {
                            stats.intervals_ns.push(dt_ns);
                            stats.last_fps = fps;
                        }
                    }
                }
                prev_timestamps.insert(label, frame.grab_timestamp_nanoseconds);
            }

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

            if multi_frame_sender.send(payload).is_err() {
                eprintln!("[gatherer] downstream disconnected, shutting down");
                for handle in &camera_handles {
                    handle.send_shutdown();
                }
                break;
            }
        }

        // ── Final Statistics ──
        eprintln!();
        eprintln!("══════════════════════════════════════════════════");
        eprintln!("  GATHERER FINAL STATISTICS");
        eprintln!("──────────────────────────────────────────────────");
        eprintln!("  Total steps: {step}");
        eprintln!();
        eprintln!("  EXPLANATION:");
        eprintln!("  - spread: max - min grab timestamp across all cameras in one multiframe.");
        eprintln!("  - multiframe fps: rate computed from inter-multiframe timestamps.");
        eprintln!("  - per-camera fps: rate for each camera from consecutive frame timestamps.");
        eprintln!("    (These all measure the same underlying cycle; small differences are");
        eprintln!("     measurement noise / OS scheduling jitter.)");
        eprintln!();
        eprintln!("  Data collected over {step} multiframe steps across {camera_count} cameras.");
        eprintln!("  All values are per-step samples unless noted.");
        eprintln!();

        // Per-camera FPS distributions
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
        eprintln!("══════════════════════════════════════════════════");
        eprintln!();

        eprintln!("[gatherer] exited after {step} steps");
    })
}
