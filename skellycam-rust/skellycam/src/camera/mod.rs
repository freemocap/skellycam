pub mod types;
pub mod thread;
pub mod enumerate;

pub use types::{
    CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket,
    MultiFramePayload,
};
pub use thread::spawn_camera_thread;
pub use enumerate::enumerate_directshow_cameras;

pub(crate) fn decode_fourcc(fourcc: u32) -> String {
    let bytes = [
        (fourcc & 0xFF) as u8,
        ((fourcc >> 8) & 0xFF) as u8,
        ((fourcc >> 16) & 0xFF) as u8,
        ((fourcc >> 24) & 0xFF) as u8,
    ];
    String::from_utf8_lossy(&bytes).to_string()
}
