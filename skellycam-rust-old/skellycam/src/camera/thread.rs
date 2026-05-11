//! Camera thread dispatcher — selects backend at compile time via Cargo features.
//!
//!   cargo build                         → nokhwa MSMF
//!   cargo build --features opencv-backend  → opencv DirectShow

use std::sync::mpsc;

use super::types::{CameraEvent, CameraHandle, CameraIdentity, FramePacket};

pub fn spawn_camera_thread(
    index: u32,
    requested_width: u32,
    requested_height: u32,
    identity: CameraIdentity,
) -> (
    CameraHandle,
    mpsc::Receiver<CameraEvent>,
    mpsc::Receiver<FramePacket>,
) {
    #[cfg(feature = "opencv-backend")]
    {
        return super::backend_opencv::spawn_camera_thread_opencv(
            index, requested_width, requested_height, identity,
        );
    }
    #[cfg(feature = "nokhwa-backend")]
    {
        return super::backend_nokhwa::spawn_camera_thread_nokhwa(
            index, requested_width, requested_height, identity,
        );
    }
    #[allow(unreachable_code)]
    {
        panic!("No camera backend enabled.");
    }
}
