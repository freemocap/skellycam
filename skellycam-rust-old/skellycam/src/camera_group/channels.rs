//! All channel definitions for a CameraGroup.
//! Channels are the Rust replacement for the Python PubSub system.
//!
//! Channel topology per group:
//!   camera thread ──sync_channel(1)──→ decoder thread ──sync_channel(1)──→ gatherer
//!                                                                          │
//!                                                     ┌────────────────────┘
//!                                                     ↓                    ↓
//!                                              recorder (mpsc)     websocket (watch)

pub struct CameraGroupChannels {}

impl CameraGroupChannels {
    pub fn new() -> Self {
        Self {}
    }
}
