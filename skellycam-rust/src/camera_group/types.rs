use crate::camera::{CameraConfig, CameraIdentity, FramePacket};
use crate::recording::finalizer::RecordingSummary;
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

/// Parameters for starting a recording session.
///
/// Carries the output directory and an optional label. The dispatcher
/// thread creates per-camera VideoRecorders and CsvWriters when it
/// receives a `StartRecording` command.
#[derive(Debug, Clone)]
pub struct RecordingParams {
    pub output_dir: String,
    pub label: Option<String>,
}

/// Command sent from the `CameraGroup` handle to the gatherer thread to
/// add or remove cameras at runtime.
pub enum GathererUpdate {
    AddCamera {
        camera_id: String,
        frame_receiver: mpsc::Receiver<FramePacket>,
    },
    RemoveCamera {
        camera_id: String,
    },
}

/// Command sent from the `CameraGroup` handle to the dispatcher thread.
pub enum DispatcherCommand {
    StartRecording { params: RecordingParams },
    StopRecording { response_tx: mpsc::Sender<RecordingSummary> },
    Shutdown,
}
