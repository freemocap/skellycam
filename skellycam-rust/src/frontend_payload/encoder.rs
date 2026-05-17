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

use crate::camera::MultiFramePayload;

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
