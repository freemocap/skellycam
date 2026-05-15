pub mod encoder;
pub mod image_pipeline;
pub mod jpeg_transform;

pub use encoder::{encode_payload, FrameHeader, PayloadHeader};
pub use image_pipeline::{jpeg_encode_rgb, resize_rgb, DEFAULT_DISPLAY_SCALE, DEFAULT_JPEG_QUALITY};

use crate::camera::{FrameData, MultiFramePayload};

/// Encode a MultiFramePayload into the frontend binary wire format.
///
/// Two paths depending on frame data format:
///   - `FrameData::Mjpg` — camera-original JPEG bytes. Optionally rotated
///     losslessly via `tjTransform`, then packed directly. No decode.
///   - `FrameData::Rgb` — legacy path: resize → JPEG encode → pack.
///
/// This is pure computation — no I/O, no async, no GIL interaction.
pub fn encode_multiframe(payload: &MultiFramePayload) -> Result<Vec<u8>, String> {
    let mut jpegs = Vec::new();
    let mut display_widths = Vec::new();
    let mut display_heights = Vec::new();

    for frame in &payload.frames {
        match &frame.data {
            FrameData::Mjpg(jpeg_bytes) => {
                // Camera-original JPEG — pass through (with optional lossless rotation).
                let output = if let Some(rotated) = jpeg_transform::rotate_jpeg_lossless(jpeg_bytes, frame.rotation) {
                    rotated
                } else {
                    jpeg_bytes.clone()
                };
                let len = output.len();
                jpegs.push(output);
                display_widths.push(frame.width);
                display_heights.push(frame.height);
                // Quick sanity: a valid JPEG starts with 0xFF 0xD8
                if len < 2 || jpeg_bytes[0] != 0xFF || jpeg_bytes[1] != 0xD8 {
                    tracing::warn!(
                        "Camera {}: frame {} does not look like JPEG (first bytes: {:02X?})",
                        frame.identity.label(),
                        frame.frame_number,
                        &jpeg_bytes[..jpeg_bytes.len().min(4)],
                    );
                }
            }
            FrameData::Rgb(rgb_bytes) => {
                // Legacy RGB path: resize + JPEG-encode
                let (resized, new_w, new_h) = resize_rgb(
                    rgb_bytes, frame.width, frame.height, DEFAULT_DISPLAY_SCALE,
                );
                let jpeg = jpeg_encode_rgb(&resized, new_w, new_h, DEFAULT_JPEG_QUALITY)?;
                jpegs.push(jpeg);
                display_widths.push(new_w);
                display_heights.push(new_h);
            }
        }
    }

    Ok(encode_payload(payload, &jpegs, &display_widths, &display_heights))
}
