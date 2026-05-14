use crate::camera::CameraIdentity;

pub struct CameraGroupConfig {
    pub camera_index: u32,
    pub requested_width: u32,
    pub requested_height: u32,
    pub identity: CameraIdentity,
}
