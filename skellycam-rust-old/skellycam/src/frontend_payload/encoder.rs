//! PayloadEncoder: assembles the binary WebSocket payload from multi-camera frames.
//! Uses a reusable Vec<u8> buffer (cleared each frame, capacity preserved).
//! See websocket/binary_protocol.rs for the struct layout definitions.

pub struct PayloadEncoder {
    buffer: Vec<u8>,
}

impl PayloadEncoder {
    pub fn new() -> Self {
        Self {
            buffer: Vec::with_capacity(2 * 1024 * 1024), // 2 MB initial capacity
        }
    }
}
