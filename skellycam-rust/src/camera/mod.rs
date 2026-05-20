pub mod ffi;
pub mod types;
pub mod camera;
pub mod camera_thread;
pub mod frame_loop;
pub mod detect;

pub use types::{
    CameraConfig, CameraCommand, CameraDetection, CameraEvent, CameraFormatInfo,
    CameraHandle, CameraIdentity, FrameData, FrameLifecycleTimestamps, FramePacket,
    MultiFramePayload,
};
pub use camera::Camera;
pub use camera_thread::spawn;
pub use detect::detect_cameras;
pub use frame_loop::{FrameState, FrameStateMachine};
