//! Binary protocol structs for WebSocket frame transmission.
//! `#[repr(C)]` matches numpy's `align=True` layout.
//! The frontend JavaScript parses these exact byte layouts.
//!
//! Layout:
//!   PayloadHeader (24 bytes) → matches Python FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE
//!   FrameHeader   (56 bytes) → matches Python FRONTEND_FRAME_HEADER_DTYPE
//!   JPEG bytes (variable, specified by jpeg_string_length)
//!   PayloadFooter (24 bytes) → same layout as PayloadHeader, message_type=2

/// Payload header or footer — 24 bytes, `#[repr(C)]` matches numpy align=True.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct PayloadHeaderFooter {
    pub message_type: u8,
    _padding_1: [u8; 7],
    pub frame_number: i64,
    pub number_of_cameras: i32,
    _padding_2: [u8; 4],
}

/// Per-camera frame header — 56 bytes, `#[repr(C)]` matches numpy align=True.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct FrameHeader {
    pub message_type: u8,
    _padding_1: [u8; 7],
    pub frame_number: i64,
    pub camera_identifier: [u8; 16],
    pub camera_index: i32,
    pub image_width: i32,
    pub image_height: i32,
    pub color_channels: i32,
    pub jpeg_string_length: i32,
    _padding_2: [u8; 4],
}

/// Message type values — must match Python's MessageType class.
pub struct MessageType;
impl MessageType {
    pub const PAYLOAD_HEADER: u8 = 0;
    pub const FRAME_HEADER: u8 = 1;
    pub const PAYLOAD_FOOTER: u8 = 2;
}

// Safety: these structs contain only plain integer types with no invalid states.
unsafe impl bytemuck::Pod for PayloadHeaderFooter {}
unsafe impl bytemuck::Zeroable for PayloadHeaderFooter {}
unsafe impl bytemuck::Pod for FrameHeader {}
unsafe impl bytemuck::Zeroable for FrameHeader {}
