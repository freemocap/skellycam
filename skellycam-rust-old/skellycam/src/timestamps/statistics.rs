//! RecordingTimestampStatistics: per-stage statistics after recording.
//! Uses a map-driven approach so adding stages automatically produces stats.

use std::collections::BTreeMap;

/// Statistics for a single metric across all frames.
#[derive(Debug, Clone)]
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
#[derive(Debug, Clone)]
pub struct RecordingTimestampStatistics {
    pub recording_name: String,
    pub number_of_cameras: usize,
    pub number_of_frames: usize,
    pub total_duration_seconds: f64,
    pub framerate: MetricStatistics,
    pub frame_duration: MetricStatistics,
    pub inter_camera_grab_range_milliseconds: MetricStatistics,
    pub stage_statistics: BTreeMap<String, MetricStatistics>,
}
