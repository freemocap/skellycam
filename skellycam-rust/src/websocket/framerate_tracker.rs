use std::collections::VecDeque;
use serde::Serialize;

const MAX_BUFFER_SIZE: usize = 100;

#[derive(Debug, Clone, Serialize)]
pub struct CurrentFramerate {
    pub mean_frame_duration_ms: f64,
    pub mean_frames_per_second: f64,
    pub frame_duration_max: f64,
    pub frame_duration_min: f64,
    pub frame_duration_mean: f64,
    pub frame_duration_stddev: f64,
    pub frame_duration_median: f64,
    pub frame_duration_coefficient_of_variation: f64,
    pub calculation_window_size: usize,
    pub framerate_source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct FramerateUpdateMessage {
    pub message_type: String,
    pub camera_group_id: String,
    pub backend_framerate: Option<CurrentFramerate>,
    pub frontend_framerate: Option<CurrentFramerate>,
    /// True camera capture rate from consecutive `frame_available_ns` timestamps.
    /// Immune to dispatcher stalls — holds the last computed value during stalls.
    pub camera_fps: Option<f64>,
}

pub struct FramerateTracker {
    durations_ms: VecDeque<f64>,
    source_label: String,
    last_timestamp_ns: Option<f64>,
    last_frame_number: Option<i64>,
}

impl FramerateTracker {
    pub fn new(source_label: &str) -> Self {
        Self {
            durations_ms: VecDeque::with_capacity(MAX_BUFFER_SIZE),
            source_label: source_label.to_string(),
            last_timestamp_ns: None,
            last_frame_number: None,
        }
    }

    /// Record a backend frame using payload timestamp and frame number.
    /// Computes true per-frame duration even when frames are skipped.
    pub fn record_backend_frame(&mut self, timestamp_ns: f64, frame_number: i64) {
        if let (Some(prev_ts), Some(prev_fn)) = (self.last_timestamp_ns, self.last_frame_number) {
            let frame_delta = frame_number - prev_fn;
            if frame_delta > 0 {
                let duration_ns = timestamp_ns - prev_ts;
                let per_frame_ms = (duration_ns / frame_delta as f64) / 1_000_000.0;
                if per_frame_ms > 0.0 && per_frame_ms < 10_000.0 {
                    self.push_duration(per_frame_ms);
                }
            }
        }
        self.last_timestamp_ns = Some(timestamp_ns);
        self.last_frame_number = Some(frame_number);
    }

    /// Record a frontend frame using wall-clock duration in milliseconds.
    pub fn record_frontend_frame(&mut self, duration_ms: f64) {
        if duration_ms > 0.0 && duration_ms < 10_000.0 {
            self.push_duration(duration_ms);
        }
    }

    /// Compute statistics and reset the buffer (each report covers only since last report).
    pub fn snapshot_and_reset(&mut self) -> Option<CurrentFramerate> {
        if self.durations_ms.is_empty() {
            return None;
        }

        let mut sorted: Vec<f64> = self.durations_ms.iter().copied().collect();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

        let n = sorted.len();
        let sum: f64 = sorted.iter().sum();
        let mean = sum / n as f64;
        let min = sorted[0];
        let max = sorted[n - 1];
        let median = if n % 2 == 0 {
            (sorted[n / 2 - 1] + sorted[n / 2]) / 2.0
        } else {
            sorted[n / 2]
        };

        let variance = sorted.iter().map(|d| (d - mean).powi(2)).sum::<f64>() / n as f64;
        let stddev = variance.sqrt();
        let coefficient_of_variation = if mean > 0.0 { stddev / mean } else { 0.0 };

        let fps = if mean > 0.0 { 1000.0 / mean } else { 0.0 };

        self.durations_ms.clear();

        Some(CurrentFramerate {
            mean_frame_duration_ms: mean,
            mean_frames_per_second: fps,
            frame_duration_max: max,
            frame_duration_min: min,
            frame_duration_mean: mean,
            frame_duration_stddev: stddev,
            frame_duration_median: median,
            frame_duration_coefficient_of_variation: coefficient_of_variation,
            calculation_window_size: n,
            framerate_source: self.source_label.clone(),
        })
    }

    fn push_duration(&mut self, duration_ms: f64) {
        if self.durations_ms.len() >= MAX_BUFFER_SIZE {
            self.durations_ms.pop_front();
        }
        self.durations_ms.push_back(duration_ms);
    }
}
