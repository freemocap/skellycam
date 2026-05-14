//! Camera channel protocol types.

use std::sync::mpsc;

/// All nanosecond-precision monotonic timestamps in a single frame's lifecycle.
///
/// The camera thread stamps fields as the frame moves through the capture loop.
/// The gatherer stamps `gatherer_received_ns` after `recv()` returns.
/// All values are from `performance_counter_nanoseconds()` —
/// nanoseconds since process start. Zero means "not yet stamped."
#[derive(Debug, Clone)]
pub struct FrameLifecycleTimestamps {
    /// Top of the capture loop iteration for this frame.
    pub loop_start_ns: i64,
    /// `Cap_hasNewFrame()` returned true — hardware has a frame ready.
    pub frame_available_ns: i64,
    /// About to call `barrier.wait()`.
    pub pre_barrier_ns: i64,
    /// Barrier released — all cameras and gatherer synchronized.
    pub post_barrier_ns: i64,
    /// About to call `Cap_captureFrame()`.
    pub pre_capture_ns: i64,
    /// `Cap_captureFrame()` returned successfully.
    pub post_capture_ns: i64,
    /// About to call `frame_sender.send()`.
    pub pre_send_ns: i64,
    /// `frame_sender.send()` returned — gatherer consumed previous frame,
    /// channel has capacity for this one.
    pub post_send_ns: i64,
    /// Stamped by the gatherer when `recv()` returns this frame.
    pub gatherer_received_ns: i64,
}

impl FrameLifecycleTimestamps {
    pub fn new() -> Self {
        Self {
            loop_start_ns: 0,
            frame_available_ns: 0,
            pre_barrier_ns: 0,
            post_barrier_ns: 0,
            pre_capture_ns: 0,
            post_capture_ns: 0,
            pre_send_ns: 0,
            post_send_ns: 0,
            gatherer_received_ns: 0,
        }
    }
}

/// Frame pixel data format.
#[derive(Debug, Clone)]
pub enum FrameData {
    Rgb(Vec<u8>),
}

impl FrameData {
    pub fn len(&self) -> usize {
        match self {
            Self::Rgb(bytes) => bytes.len(),
        }
    }

    pub fn as_bytes(&self) -> &[u8] {
        match self {
            Self::Rgb(bytes) => bytes,
        }
    }
}

/// A single camera frame traveling through the pipeline.
#[derive(Debug, Clone)]
pub struct FramePacket {
    pub data: FrameData,
    pub width: u32,
    pub height: u32,
    pub timestamps: FrameLifecycleTimestamps,
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

/// Multi-camera synchronized payload with gatherer-level timestamps.
#[derive(Debug)]
pub struct MultiFramePayload {
    pub frames: Vec<FramePacket>,
    pub step: i64,
    /// Stamped when the last camera's `recv()` completes.
    pub all_frames_received_ns: i64,
    /// Stamped after the `MultiFramePayload` struct is assembled.
    pub payload_assembled_ns: i64,
    /// Stamped just before `multi_frame_sender.send()`.
    pub pre_send_downstream_ns: i64,
    /// Stamped after `send()` returns to the downstream consumer.
    pub post_send_downstream_ns: i64,
}

impl MultiFramePayload {
    /// Hardware synchronization spread: max - min of `frame_available_ns`
    /// across cameras in this multiframe.
    ///
    /// Measures the end-to-end physical variability of when each camera
    /// delivered its frame — sensor exposure timing + USB bus scheduling +
    /// driver buffering + decode. This is bounded by roughly one frame
    /// period (33ms at 30fps) because all threads start waiting after the
    /// same barrier release. The camera whose next frame arrives soonest
    /// gets a low value; the camera whose phase offset puts it furthest
    /// gets a high value.
    pub fn hardware_sync_spread_ns(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let min = self
            .frames
            .iter()
            .map(|f| f.timestamps.frame_available_ns)
            .min()
            .unwrap();
        let max = self
            .frames
            .iter()
            .map(|f| f.timestamps.frame_available_ns)
            .max()
            .unwrap();
        max - min
    }

    /// Software synchronization spread: max - min of `pre_capture_ns`
    /// across cameras in this multiframe.
    ///
    /// `pre_capture_ns` is stamped after the barrier releases all threads
    /// simultaneously, right before `Cap_captureFrame()`. The spread
    /// measures pure OS thread scheduling jitter — how far apart in time
    /// the OS scheduler picks up each camera thread after the barrier
    /// unblocks them. In a system with hardware trigger control this is
    /// the metric that tells you your software's contribution to total
    /// jitter. With USB webcams the hardware spread dominates; this is
    /// the engineering quality metric for the synchronization mechanism.
    pub fn software_sync_spread_ns(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let min = self
            .frames
            .iter()
            .map(|f| f.timestamps.pre_capture_ns)
            .min()
            .unwrap();
        let max = self
            .frames
            .iter()
            .map(|f| f.timestamps.pre_capture_ns)
            .max()
            .unwrap();
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
