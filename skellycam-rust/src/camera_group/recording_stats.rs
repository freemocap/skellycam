//! Recording-scoped statistics accumulator.
//!
//! Mirrors the gatherer's per-lifecycle stats collection but scoped to a single
//! recording session. Fed by the dispatcher via `push_multiframe()` for each
//! multiframe received during recording. On `finalize()`, computes the same
//! summary statistics the gatherer prints at exit.
//!
//! Unlike the gatherer's lifecycle stats (which now use a ring buffer), these
//! Vecs are bounded by recording duration — a 10-minute recording at 30 fps
//! produces 18,000 samples per metric, ~144 KB total. Negligible.

use crate::camera::MultiFramePayload;

// ── Stats computation (same primitives as the gatherer) ──────────────────

#[derive(Debug, Clone, serde::Serialize)]
pub struct StatsSummary {
    pub median: f64,
    pub mean: f64,
    pub std: f64,
    pub cv_pct: f64,
    pub min: f64,
    pub max: f64,
    pub n: usize,
}

fn compute_stats(values: &[f64]) -> Option<StatsSummary> {
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

    Some(StatsSummary {
        median,
        mean,
        std,
        cv_pct,
        min,
        max,
        n,
    })
}

// ── Per-camera stats row ─────────────────────────────────────────────────

#[derive(Debug, Clone, serde::Serialize)]
pub struct PerCameraStatsRow {
    pub camera_label: String,
    pub camera_index: i32,
    pub wait_for_frame: Option<StatsSummary>,
    pub jpeg_extract: Option<StatsSummary>,
    pub channel_send_wait: Option<StatsSummary>,
    pub cycle_total: Option<StatsSummary>,
}

// ── RecordingStats accumulator ───────────────────────────────────────────

pub struct RecordingStats {
    camera_count: usize,
    camera_labels: Vec<String>,
    camera_indices: Vec<i32>,

    per_camera_wait_for_frame: Vec<Vec<f64>>,
    per_camera_jpeg_extract: Vec<Vec<f64>>,
    per_camera_channel_send_wait: Vec<Vec<f64>>,
    per_camera_cycle_total: Vec<Vec<f64>>,

    frame_arrival_spread: Vec<f64>,
    thread_wakeup_spread: Vec<f64>,
    multiframe_interval_ns: Vec<f64>,

    gatherer_frames_collection: Vec<f64>,
    gatherer_payload_assembly: Vec<f64>,
    gatherer_downstream_send: Vec<f64>,

    prev_loop_starts: Vec<Option<i64>>,
    prev_first_frame_avail_ns: Option<i64>,
}

impl RecordingStats {
    pub fn new(camera_count: usize) -> Self {
        Self {
            camera_count,
            camera_labels: vec!["?".to_string(); camera_count],
            camera_indices: vec![-1; camera_count],
            per_camera_wait_for_frame: vec![Vec::new(); camera_count],
            per_camera_jpeg_extract: vec![Vec::new(); camera_count],
            per_camera_channel_send_wait: vec![Vec::new(); camera_count],
            per_camera_cycle_total: vec![Vec::new(); camera_count],
            frame_arrival_spread: Vec::new(),
            thread_wakeup_spread: Vec::new(),
            multiframe_interval_ns: Vec::new(),
            gatherer_frames_collection: Vec::new(),
            gatherer_payload_assembly: Vec::new(),
            gatherer_downstream_send: Vec::new(),
            prev_loop_starts: vec![None; camera_count],
            prev_first_frame_avail_ns: None,
        }
    }

    /// Feed one multiframe's timing data into the accumulator.
    ///
    /// Called by the dispatcher for every multiframe while recording is active.
    /// `post_send_downstream_ns` is stamped by the dispatcher after encoding
    /// and storing the frontend payload.
    pub fn push_multiframe(
        &mut self,
        payload: &MultiFramePayload,
        post_send_downstream_ns: i64,
    ) {
        // Snapshot camera labels on first multiframe
        for (i, frame) in payload.frames.iter().enumerate() {
            if i < self.camera_labels.len() && self.camera_labels[i] == "?" {
                self.camera_labels[i] = frame.identity.label();
                self.camera_indices[i] = frame.identity.camera_index;
            }
        }

        // Per-camera per-frame metrics
        for (i, frame) in payload.frames.iter().enumerate() {
            if i >= self.camera_count {
                break;
            }
            let ts = &frame.timestamps;

            if ts.loop_start_ns > 0 && ts.frame_available_ns >= ts.loop_start_ns {
                self.per_camera_wait_for_frame[i]
                    .push((ts.frame_available_ns - ts.loop_start_ns) as f64);
            }
            if ts.frame_available_ns > 0 && ts.post_jpeg_extract_ns >= ts.frame_available_ns {
                self.per_camera_jpeg_extract[i]
                    .push((ts.post_jpeg_extract_ns - ts.frame_available_ns) as f64);
            }
            if ts.pre_send_ns > 0 && ts.gatherer_received_ns >= ts.pre_send_ns {
                self.per_camera_channel_send_wait[i]
                    .push((ts.gatherer_received_ns - ts.pre_send_ns) as f64);
            }
            if let Some(prev) = self.prev_loop_starts[i] {
                if ts.loop_start_ns > prev {
                    self.per_camera_cycle_total[i]
                        .push((ts.loop_start_ns - prev) as f64);
                }
            }
            self.prev_loop_starts[i] = Some(ts.loop_start_ns);
        }

        // Multiframe-level metrics
        self.frame_arrival_spread.push(payload.frame_arrival_spread_ns() as f64);
        self.thread_wakeup_spread.push(payload.thread_wakeup_spread_ns() as f64);
        if let Some(prev_ts) = self.prev_first_frame_avail_ns {
            let first = payload
                .frames
                .first()
                .map(|f| f.timestamps.frame_available_ns)
                .unwrap_or(0);
            if first > prev_ts {
                self.multiframe_interval_ns.push((first - prev_ts) as f64);
            }
        }
        self.prev_first_frame_avail_ns = payload
            .frames
            .first()
            .map(|f| f.timestamps.frame_available_ns);

        // Gatherer-level metrics
        if payload.all_frames_received_ns > 0
            && payload.all_frames_received_ns >= payload.frames.first().map(|f| f.timestamps.frame_available_ns).unwrap_or(0)
        {
            let first_avail = payload.frames.first().map(|f| f.timestamps.frame_available_ns).unwrap_or(0);
            self.gatherer_frames_collection
                .push((payload.all_frames_received_ns - first_avail) as f64);
        }
        if payload.payload_assembled_ns > 0
            && payload.payload_assembled_ns >= payload.all_frames_received_ns
        {
            self.gatherer_payload_assembly
                .push((payload.payload_assembled_ns - payload.all_frames_received_ns) as f64);
        }
        if payload.pre_send_downstream_ns > 0
            && post_send_downstream_ns >= payload.pre_send_downstream_ns
        {
            self.gatherer_downstream_send
                .push((post_send_downstream_ns - payload.pre_send_downstream_ns) as f64);
        }
    }

    /// Compute the final summary for inclusion in `RecordingSummary`.
    pub fn finalize(self) -> RecordingStatsSummary {
        let multiframe_fps: Vec<f64> = self
            .multiframe_interval_ns
            .iter()
            .filter(|dt| **dt > 0.0)
            .map(|dt_ns| 1_000_000_000.0 / dt_ns)
            .collect();

        let per_camera: Vec<PerCameraStatsRow> = (0..self.camera_count)
            .map(|i| PerCameraStatsRow {
                camera_label: self.camera_labels.get(i).cloned().unwrap_or_default(),
                camera_index: self.camera_indices.get(i).copied().unwrap_or(-1),
                wait_for_frame: compute_stats(
                    self.per_camera_wait_for_frame.get(i).map(|v| v.as_slice()).unwrap_or(&[]),
                ),
                jpeg_extract: compute_stats(
                    self.per_camera_jpeg_extract.get(i).map(|v| v.as_slice()).unwrap_or(&[]),
                ),
                channel_send_wait: compute_stats(
                    self.per_camera_channel_send_wait.get(i).map(|v| v.as_slice()).unwrap_or(&[]),
                ),
                cycle_total: compute_stats(
                    self.per_camera_cycle_total.get(i).map(|v| v.as_slice()).unwrap_or(&[]),
                ),
            })
            .collect();

        RecordingStatsSummary {
            multiframe_fps: compute_stats(&multiframe_fps),
            multiframe_duration_ns: compute_stats(&self.multiframe_interval_ns),
            frame_arrival_spread: compute_stats(&self.frame_arrival_spread),
            thread_wakeup_spread: compute_stats(&self.thread_wakeup_spread),
            gatherer_frames_collection: compute_stats(&self.gatherer_frames_collection),
            gatherer_payload_assembly: compute_stats(&self.gatherer_payload_assembly),
            gatherer_downstream_send: compute_stats(&self.gatherer_downstream_send),
            total_multiframes: self.multiframe_interval_ns.len(),
            per_camera,
        }
    }
}

// ── Serializable summary ─────────────────────────────────────────────────

#[derive(Debug, Clone, serde::Serialize)]
pub struct RecordingStatsSummary {
    pub total_multiframes: usize,
    pub multiframe_fps: Option<StatsSummary>,
    pub multiframe_duration_ns: Option<StatsSummary>,
    pub frame_arrival_spread: Option<StatsSummary>,
    pub thread_wakeup_spread: Option<StatsSummary>,
    pub gatherer_frames_collection: Option<StatsSummary>,
    pub gatherer_payload_assembly: Option<StatsSummary>,
    pub gatherer_downstream_send: Option<StatsSummary>,
    pub per_camera: Vec<PerCameraStatsRow>,
}
