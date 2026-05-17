use crate::camera::{CameraConfig, CameraIdentity, FramePacket};
use std::sync::mpsc;

/// Configuration for a single camera within the group.
///
/// Bundles the hardware identity (from detection) with the capture
/// settings (resolution, exposure, framerate, etc.).
#[derive(Debug, Clone)]
pub struct CameraGroupConfig {
    pub identity: CameraIdentity,
    pub capture_config: CameraConfig,
}

/// Recording parameters — placeholder for future recording functionality.
///
/// The actual recording pipeline (writing frames to disk, codec selection,
/// file format) will be added in a later iteration. For now, this struct
/// marks the recording intent and carries the output directory.
#[derive(Debug, Clone)]
pub struct RecordingInfo {
    /// Directory where recording output will be written.
    pub output_dir: String,
    /// Optional human-readable label for the recording session.
    pub label: Option<String>,
}

/// Command sent from the `CameraGroup` handle to the gatherer thread to
/// add or remove cameras at runtime.
///
/// The gatherer checks for these between frame cycles via `try_recv()`.
/// This is a channel-based approach — no locks, no shared mutable state.
pub enum GathererUpdate {
    AddCamera {
        camera_id: String,
        frame_receiver: mpsc::Receiver<FramePacket>,
    },
    RemoveCamera {
        camera_id: String,
    },
}
