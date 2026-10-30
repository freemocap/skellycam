//! Binary protocol encoder for frontend WebSocket payloads.
//!
//! Produces a linear byte sequence matching the Python `create_frontend_payload()`
//! layout bit-for-bit, so the existing Electron/React frontend can consume it
//! without changes.
//!
//! Wire format:
//!   PayloadHeader (24 bytes, message_type=0)
//!   FrameHeader (56 bytes, message_type=1) + JPEG bytes  (repeated per camera)
//!   PayloadHeader (24 bytes, message_type=2)  — footer

use crate::camera::{FrameData, MultiFramePayload};

/// 24-byte header/footer that brackets every payload.
///
/// Uses `#[repr(C)]` to match the Python numpy `FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE`
/// with `align=True` (8-byte alignment for the i64).
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct PayloadHeader {
    pub message_type: u8,
    _padding1: [u8; 7],
    pub frame_number: i64,
    pub number_of_cameras: i32,
    _padding2: [u8; 4],
}

const _: () = assert!(std::mem::size_of::<PayloadHeader>() == 24);

impl PayloadHeader {
    pub fn to_bytes(&self) -> [u8; 24] {
        let ptr = self as *const Self as *const u8;
        let mut bytes = [0u8; 24];
        bytes.copy_from_slice(unsafe { std::slice::from_raw_parts(ptr, 24) });
        bytes
    }
}

/// 56-byte header that precedes each camera's JPEG data.
///
/// Uses `#[repr(C)]` to match the Python numpy `FRONTEND_FRAME_HEADER_DTYPE`
/// with `align=True`.
#[repr(C)]
#[derive(Debug, Clone)]
pub struct FrameHeader {
    pub message_type: u8,
    _padding1: [u8; 7],
    pub frame_number: i64,
    pub camera_identifier: [u8; 16],
    pub camera_index: i32,
    pub image_width: i32,
    pub image_height: i32,
    pub color_channels: i32,
    pub jpeg_string_length: i32,
    _padding2: [u8; 4],
}

const _: () = assert!(std::mem::size_of::<FrameHeader>() == 56);

impl FrameHeader {
    pub fn to_bytes(&self) -> [u8; 56] {
        let ptr = self as *const Self as *const u8;
        let mut bytes = [0u8; 56];
        bytes.copy_from_slice(unsafe { std::slice::from_raw_parts(ptr, 56) });
        bytes
    }
}

/// Build a camera identifier byte array from the unique_identifier string.
/// Truncates or null-pads to exactly 16 bytes (Python uses `S16` = fixed 16-byte string).
fn make_camera_id(unique_identifier: &str) -> [u8; 16] {
    let mut id = [0u8; 16];
    let src = unique_identifier.as_bytes();
    let len = src.len().min(16);
    id[..len].copy_from_slice(&src[..len]);
    id
}

/// Encode a `MultiFramePayload` into the binary frontend wire format.
///
/// Returns a `Vec<u8>` containing:
///   PayloadHeader → per-camera FrameHeader + JPEG → PayloadFooter
///
/// `jpeg_per_camera` must have one `Vec<u8>` per frame, in the same order
/// as `payload.frames`. Each JPEG's length is written into the corresponding
/// `FrameHeader.jpeg_string_length` field.
pub fn encode_payload(
    payload: &MultiFramePayload,
    jpeg_per_camera: &[Vec<u8>],
    display_widths: &[u32],
    display_heights: &[u32],
) -> Vec<u8> {
    let camera_count = payload.frames.len();
    let frame_number = payload.frames.first().map(|f| f.frame_number).unwrap_or(0);

    let estimated = 24 + camera_count * (56 + 50_000) + 24;
    let mut buf = Vec::with_capacity(estimated);

    // ── Payload Header ──
    let header = PayloadHeader {
        message_type: 0,
        _padding1: [0u8; 7],
        frame_number,
        number_of_cameras: camera_count as i32,
        _padding2: [0u8; 4],
    };
    buf.extend_from_slice(&header.to_bytes());

    // ── Per-camera FrameHeader + JPEG ──
    for (i, frame) in payload.frames.iter().enumerate() {
        let jpeg = &jpeg_per_camera[i];
        let display_w = if i < display_widths.len() { display_widths[i] } else { frame.width };
        let display_h = if i < display_heights.len() { display_heights[i] } else { frame.height };

        let fh = FrameHeader {
            message_type: 1,
            _padding1: [0u8; 7],
            frame_number: frame.frame_number,
            camera_identifier: make_camera_id(&frame.identity.camera_id),
            camera_index: frame.identity.camera_index,
            image_width: display_w as i32,
            image_height: display_h as i32,
            color_channels: 3,
            jpeg_string_length: jpeg.len() as i32,
            _padding2: [0u8; 4],
        };
        buf.extend_from_slice(&fh.to_bytes());
        buf.extend_from_slice(jpeg);
    }

    // ── Payload Footer ──
    let footer = PayloadHeader {
        message_type: 2,
        _padding1: [0u8; 7],
        frame_number,
        number_of_cameras: camera_count as i32,
        _padding2: [0u8; 4],
    };
    buf.extend_from_slice(&footer.to_bytes());

    buf
}

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
                let output = jpeg_bytes.clone();
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
                let (resized, new_w, new_h) = crate::frontend_payload::image_pipeline::resize_rgb(
                    rgb_bytes,
                    frame.width,
                    frame.height,
                    crate::frontend_payload::image_pipeline::DEFAULT_DISPLAY_SCALE,
                );
                let jpeg = crate::frontend_payload::image_pipeline::jpeg_encode_rgb(
                    &resized,
                    new_w,
                    new_h,
                    crate::frontend_payload::image_pipeline::DEFAULT_JPEG_QUALITY,
                )?;
                jpegs.push(jpeg);
                display_widths.push(new_w);
                display_heights.push(new_h);
            }
        }
    }

    Ok(encode_payload(payload, &jpegs, &display_widths, &display_heights))
}
