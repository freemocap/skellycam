use crate::camera::{CameraConfig, CameraIdentity};

#[derive(Debug, Clone)]
pub struct CameraGroupConfig {
    pub capture_config: CameraConfig,
    pub identity: CameraIdentity,
}
