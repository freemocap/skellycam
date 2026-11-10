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

/// One camera's encoded preview image, in packing order.
pub struct PreviewImage {
    pub camera_id: String,
    pub camera_index: i32,
    pub width: u32,
    pub height: u32,
    pub jpeg: Vec<u8>,
}

/// The wire's camera slot: 1-16 non-null ASCII bytes, null-padded, as the Python encoder requires.
fn camera_id_slot(camera_id: &str) -> Result<[u8; 16], String> {
    let bytes = camera_id.as_bytes();
    if bytes.is_empty() || bytes.len() > 16 || !camera_id.is_ascii() || bytes.contains(&0) {
        return Err(format!("Image transport IDs must contain 1-16 non-null ASCII bytes: {camera_id:?}"));
    }
    let mut slot = [0u8; 16];
    slot[..bytes.len()].copy_from_slice(bytes);
    Ok(slot)
}

/// Pack one frameset: payload header, a frame header and JPEG per camera, payload footer.
pub fn pack_payload(frame_number: i64, images: &[PreviewImage]) -> Result<Vec<u8>, String> {
    let mut buf = Vec::with_capacity(48 + images.iter().map(|image| 56 + image.jpeg.len()).sum::<usize>());
    let mut header = PayloadHeader {
        message_type: 0,
        _padding1: [0u8; 7],
        frame_number,
        number_of_cameras: images.len() as i32,
        _padding2: [0u8; 4],
    };
    buf.extend_from_slice(&header.to_bytes());
    for image in images {
        let frame_header = FrameHeader {
            message_type: 1,
            _padding1: [0u8; 7],
            frame_number,
            camera_identifier: camera_id_slot(&image.camera_id)?,
            camera_index: image.camera_index,
            image_width: image.width as i32,
            image_height: image.height as i32,
            color_channels: 3,
            jpeg_string_length: image.jpeg.len() as i32,
            _padding2: [0u8; 4],
        };
        buf.extend_from_slice(&frame_header.to_bytes());
        buf.extend_from_slice(&image.jpeg);
    }
    header.message_type = 2;
    buf.extend_from_slice(&header.to_bytes());
    Ok(buf)
}
