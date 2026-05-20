use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

// ── Detection ──────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct CameraFormatSchema {
    pub width: i32,
    pub height: i32,
    pub fps: i32,
    pub fourcc: i32,
    pub fourcc_str: String,
}

impl From<&crate::camera::CameraFormatInfo> for CameraFormatSchema {
    fn from(f: &crate::camera::CameraFormatInfo) -> Self {
        Self {
            width: f.width as i32,
            height: f.height as i32,
            fps: f.fps as i32,
            fourcc: f.fourcc as i32,
            fourcc_str: f.fourcc_str.clone(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct DetectedCamera {
    pub index: i32,
    pub name: String,
    pub vendor_id: Option<i32>,
    pub product_id: Option<i32>,
    pub path: Option<String>,
    pub backend_id: Option<i32>,
    pub backend_name: Option<String>,
    pub formats: Vec<CameraFormatSchema>,
    pub camera_id: String,
    pub available: bool,
}

impl From<crate::camera::CameraDetection> for DetectedCamera {
    fn from(d: crate::camera::CameraDetection) -> Self {
        let c = d.identity;
        Self {
            index: c.camera_index,
            name: c.camera_name,
            vendor_id: None,
            product_id: None,
            path: if c.device_path.is_empty() {
                None
            } else {
                Some(c.device_path)
            },
            backend_id: None,
            backend_name: None,
            formats: c.formats.iter().map(CameraFormatSchema::from).collect(),
            camera_id: c.camera_id,
            available: d.available,
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct DetectedCamerasResponse {
    pub cameras: Vec<DetectedCamera>,
}

// ── Group create/apply ─────────────────────────────────────────────────────

/// Input format for a single camera within a group-apply request.
///
/// Matches the Python `CameraConfig-Input` schema field-for-field so the
/// frontend can send the same payload to either backend. Fields the Rust
/// backend doesn't use (color_channels, pixel_format, capture_fourcc,
/// writer_fourcc) are accepted but ignored.
#[derive(Debug, Deserialize, ToSchema)]
pub struct CameraConfigInput {
    pub camera_id: String,
    #[serde(default)]
    pub camera_index: i32,
    #[serde(default)]
    pub camera_name: String,
    #[serde(default = "default_true")]
    pub use_this_camera: bool,
    #[serde(default = "default_resolution")]
    pub resolution: ResolutionInput,
    #[serde(default)]
    pub color_channels: i32,
    #[serde(default)]
    pub pixel_format: String,
    #[serde(default = "default_exposure_mode")]
    pub exposure_mode: String,
    #[serde(default = "default_exposure")]
    pub exposure: i32,
    #[serde(default = "default_framerate")]
    pub framerate: f64,
    #[serde(default = "default_rotation")]
    pub rotation: i32,
    #[serde(default)]
    pub capture_fourcc: String,
    #[serde(default)]
    pub writer_fourcc: String,
}

fn default_true() -> bool {
    true
}
fn default_resolution() -> ResolutionInput {
    ResolutionInput {
        height: 720,
        width: 1280,
    }
}
fn default_exposure_mode() -> String {
    "MANUAL".into()
}
fn default_exposure() -> i32 {
    -7
}
fn default_framerate() -> f64 {
    -1.0
}
fn default_rotation() -> i32 {
    -1
}

/// Simple width/height pair matching `ImageResolution` in the Python API.
#[derive(Debug, Deserialize, Serialize, ToSchema)]
pub struct ResolutionInput {
    #[serde(default = "default_height")]
    pub height: i32,
    #[serde(default = "default_width")]
    pub width: i32,
}

fn default_height() -> i32 {
    720
}
fn default_width() -> i32 {
    1280
}

/// Group-apply request body — matches Python `CameraGroupCreateRequest`.
///
/// `camera_configs` is a dict keyed by camera_id, matching the frontend's
/// existing payload shape.
#[derive(Debug, Deserialize, ToSchema)]
pub struct CameraGroupApplyRequest {
    pub camera_configs: HashMap<String, CameraConfigInput>,
}

/// Output format for a single camera config — matches Python `CameraConfig-Output`.
#[derive(Debug, Serialize, ToSchema)]
pub struct CameraConfigOutput {
    pub camera_id: String,
    pub camera_index: i32,
    pub camera_name: String,
    #[serde(default = "default_true")]
    pub use_this_camera: bool,
    pub resolution: ResolutionInput,
    #[serde(default)]
    pub color_channels: i32,
    #[serde(default)]
    pub pixel_format: String,
    pub exposure_mode: String,
    pub exposure: i32,
    pub framerate: f64,
    pub rotation: i32,
    #[serde(default)]
    pub capture_fourcc: String,
    #[serde(default)]
    pub writer_fourcc: String,
}

impl From<&crate::camera::CameraConfig> for CameraConfigOutput {
    fn from(c: &crate::camera::CameraConfig) -> Self {
        Self {
            camera_id: c.camera_id.clone(),
            camera_index: c.camera_index as i32,
            camera_name: String::new(),
            use_this_camera: true,
            resolution: ResolutionInput {
                height: c.height as i32,
                width: c.width as i32,
            },
            color_channels: 3,
            pixel_format: "RGB".into(),
            exposure_mode: c.exposure_mode.clone(),
            exposure: c.exposure,
            framerate: c.framerate,
            rotation: c.rotation,
            capture_fourcc: "MJPG".into(),
            writer_fourcc: "X264".into(),
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct CreateCameraGroupResponse {
    pub group_id: String,
    pub camera_configs: HashMap<String, CameraConfigOutput>,
}

// ── Recording ──────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize, ToSchema)]
pub struct StartRecordingRequest {
    #[serde(default)]
    pub recording_name: String,
    #[serde(default)]
    pub recording_directory: String,
    #[serde(default = "default_mic_index")]
    pub mic_device_index: i32,
}

fn default_mic_index() -> i32 {
    -1
}

#[derive(Debug, Serialize, ToSchema)]
pub struct StopRecordingResponse {
    pub recording_name: String,
    pub recording_path: String,
    pub number_of_cameras: i32,
    pub number_of_frames: i32,
    pub total_duration_sec: f64,
    pub mean_framerate: f64,
    pub mean_inter_camera_sync_ms: f64,
    pub framerate_stats: StatsSummary,
    pub frame_duration_stats: StatsSummary,
    pub inter_camera_grab_range_ms_stats: StatsSummary,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct StatsSummary {
    pub median: f64,
    pub mean: f64,
    pub std: f64,
    pub min: f64,
    pub max: f64,
}

// ── Close ──────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, ToSchema)]
pub struct CloseAllResponse {
    pub success: bool,
}
