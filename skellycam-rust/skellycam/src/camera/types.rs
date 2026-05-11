//! Camera channel protocol types.

use std::sync::mpsc;

/// Frame pixel data format.
#[derive(Debug, Clone)]
pub enum FrameData {
    Bgr(Vec<u8>),
}

impl FrameData {
    pub fn len(&self) -> usize {
        match self {
            Self::Bgr(bytes) => bytes.len(),
        }
    }
}

/// A single camera frame traveling through the pipeline.
#[derive(Debug, Clone)]
pub struct FramePacket {
    pub data: FrameData,
    pub width: u32,
    pub height: u32,
    pub grab_timestamp_nanoseconds: i64,
    pub identity: CameraIdentity,
    pub frame_number: i64,
}

/// Three-part camera identification.
#[derive(Debug, Clone)]
pub struct CameraIdentity {
    pub display_name: String,
    pub camera_index: i32,
    pub unique_identifier: String,
    pub device_path: String,
}

impl CameraIdentity {
    pub fn label(&self) -> String {
        format!("{} [{}]", self.display_name, self.unique_identifier)
    }
}

/// Multi-camera synchronized payload.
#[derive(Debug)]
pub struct MultiFramePayload {
    pub frames: Vec<FramePacket>,
    pub step: i64,
}

impl MultiFramePayload {
    pub fn inter_camera_grab_spread_nanoseconds(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let min = self.frames.iter().map(|f| f.grab_timestamp_nanoseconds).min().unwrap();
        let max = self.frames.iter().map(|f| f.grab_timestamp_nanoseconds).max().unwrap();
        max - min
    }
}

#[derive(Debug)]
pub enum CameraCommand {
    Shutdown,
}

#[derive(Debug)]
pub enum CameraEvent {
    Error(String),
}

#[derive(Debug, Clone)]
pub struct CameraHandle {
    pub command_sender: mpsc::Sender<CameraCommand>,
    pub identity: CameraIdentity,
    pub width: u32,
    pub height: u32,
}

impl CameraHandle {
    pub fn send_shutdown(&self) {
        let _ = self.command_sender.send(CameraCommand::Shutdown);
    }
}
