pub mod ffi;
pub mod types;
pub mod thread;
pub mod enumerate;
pub mod state_machine;

pub use types::{
    CameraCaptureConfig, CameraCommand, CameraEvent, CameraFormatInfo, CameraHandle,
    CameraIdentity, FrameData, FrameLifecycleTimestamps, FramePacket, MultiFramePayload,
};
pub use thread::spawn_camera_thread;
pub use enumerate::enumerate_directshow_cameras;
pub use state_machine::{
    Camera, Configuring, Disconnected, Enumerated, Faulted, FrameState, FrameStateMachine,
    LifecycleTransition, ShuttingDown, StateDiagram, Streaming,
};
