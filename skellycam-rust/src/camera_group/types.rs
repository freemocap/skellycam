use crate::camera::{CameraCaptureConfig, CameraIdentity};

pub struct CameraGroupConfig {
    pub capture_config: CameraCaptureConfig,
    pub identity: CameraIdentity,
}
