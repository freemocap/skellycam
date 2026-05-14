pub mod encoder;
pub mod image_pipeline;

pub use encoder::{encode_payload, FrameHeader, PayloadHeader};
pub use image_pipeline::{jpeg_encode_rgb, resize_rgb, DEFAULT_DISPLAY_SCALE, DEFAULT_JPEG_QUALITY};

use crate::camera::MultiFramePayload;

/// Encode a MultiFramePayload into the frontend binary wire format.
///
/// For each frame: resize RGB at DEFAULT_DISPLAY_SCALE, JPEG-encode at
/// DEFAULT_JPEG_QUALITY, then pack everything into the binary protocol
/// (PayloadHeader → per-camera FrameHeader + JPEG → PayloadFooter).
///
/// This is pure computation — no I/O, no async, no GIL interaction.
/// It can run on any OS thread, making it suitable for both the axum HTTP
/// server and the PyO3 Python bridge.
pub fn encode_multiframe(payload: &MultiFramePayload) -> Result<Vec<u8>, String> {
    let mut jpegs = Vec::new();
    let mut display_widths = Vec::new();
    let mut display_heights = Vec::new();

    for frame in &payload.frames {
        let rgb = frame.data.as_bytes();
        let (resized, new_w, new_h) = resize_rgb(rgb, frame.width, frame.height, DEFAULT_DISPLAY_SCALE);
        let jpeg = jpeg_encode_rgb(&resized, new_w, new_h, DEFAULT_JPEG_QUALITY)?;
        jpegs.push(jpeg);
        display_widths.push(new_w);
        display_heights.push(new_h);
    }

    Ok(encode_payload(payload, &jpegs, &display_widths, &display_heights))
}
