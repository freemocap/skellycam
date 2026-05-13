use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Serialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct DetectedCamera {
    pub camera_index: i32,
    pub display_name: String,
    pub unique_identifier: String,
    pub device_path: String,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct DetectedCamerasResponse {
    pub cameras: Vec<DetectedCamera>,
    pub camera_count: usize,
}

#[derive(Debug, Deserialize, ToSchema)]
#[serde(rename_all = "camelCase")]
pub struct CameraGroupApplyRequest {
    pub camera_indices: Vec<u32>,
    pub exposure: Option<i32>,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct CreateCameraGroupResponse {
    pub group_id: String,
    pub camera_count: usize,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct CloseAllResponse {
    pub success: bool,
}
