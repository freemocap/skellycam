//! Request/response models for all HTTP endpoints.
//! Mirror Python's Pydantic BaseModel classes exactly for frontend compatibility.

use serde::{Deserialize, Serialize};

// ---- Camera Group ----

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CameraGroupCreateRequest {
    pub camera_configs: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateCameraGroupResponse {
    pub group_id: String,
    pub camera_configs: std::collections::HashMap<String, serde_json::Value>,
}

// ---- Recording ----

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StartRecordingRequest {
    pub recording_name: String,
    pub recording_directory: String,
    pub mic_device_index: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StopRecordingResponse {
    pub recording_name: String,
    pub recording_path: String,
    pub number_of_cameras: usize,
    pub number_of_frames: usize,
    pub total_duration_seconds: f64,
    pub mean_framerate: f64,
    pub mean_inter_camera_sync_milliseconds: f64,
    pub framerate_statistics: StatisticsSummary,
    pub frame_duration_statistics: StatisticsSummary,
    pub inter_camera_grab_range_milliseconds_statistics: StatisticsSummary,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatisticsSummary {
    pub median: f64,
    pub mean: f64,
    pub standard_deviation: f64,
    pub minimum: f64,
    pub maximum: f64,
}
