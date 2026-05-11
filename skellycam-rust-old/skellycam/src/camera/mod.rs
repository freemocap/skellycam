pub mod types;
pub mod thread;

#[cfg(feature = "nokhwa-backend")]
pub mod backend_nokhwa;
#[cfg(feature = "opencv-backend")]
pub mod backend_opencv;

pub use types::{
    CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket,
    MultiFramePayload,
};
pub use thread::spawn_camera_thread;
