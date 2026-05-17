use crate::camera::{CameraCaptureConfig, CameraIdentity};

#[derive(Debug, Clone)]
pub struct CameraGroupConfig {
    pub capture_config: CameraCaptureConfig,
    pub identity: CameraIdentity,
}
