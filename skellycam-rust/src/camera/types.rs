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
    /// Time from the previous barrier release to the start of this frame's
    /// capture call. Measures jitter in how quickly the OS scheduler picks
    /// up each camera thread to begin its next capture cycle.
    pub post_barrier_to_capture_ns: i64,
    /// About to call `barrier.wait()`.
    pub pre_barrier_ns: i64,
    /// Barrier released — all cameras and gatherer synchronized.
    pub post_barrier_ns: i64,
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
            post_barrier_to_capture_ns: 0,
            pre_barrier_ns: 0,
            post_barrier_ns: 0,
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
    /// Decoded 24-bit RGB (width * height * 3 bytes).
    Rgb(Vec<u8>),
    /// Raw MJPEG bytes — each frame is a valid JPEG.
    Mjpg(Vec<u8>),
}

impl FrameData {
    pub fn len(&self) -> usize {
        match self {
            Self::Rgb(bytes) => bytes.len(),
            Self::Mjpg(bytes) => bytes.len(),
        }
    }

    pub fn as_bytes(&self) -> &[u8] {
        match self {
            Self::Rgb(bytes) => bytes,
            Self::Mjpg(bytes) => bytes,
        }
    }

    pub fn is_jpeg(&self) -> bool {
        matches!(self, Self::Mjpg(_))
    }
}

/// A single camera frame traveling through the pipeline.
#[derive(Debug, Clone)]
pub struct FramePacket {
    pub data: FrameData,
    pub width: u32,
    pub height: u32,
    pub rotation: i32,
    pub timestamps: FrameLifecycleTimestamps,
    pub identity: CameraIdentity,
    pub frame_number: i64,
}

/// A single format entry as reported by openpnp-capture.
/// Mirrors `CapFormatInfo` but with a friendly FOURCC string.
#[derive(Debug, Clone)]
pub struct CameraFormatInfo {
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub fourcc: u32,
    pub fourcc_str: String,
}

/// Camera identification with available format list.
#[derive(Debug, Clone)]
pub struct CameraIdentity {
    pub camera_name: String,
    pub camera_index: i32,
    pub camera_id: String,
    pub device_path: String,
    pub formats: Vec<CameraFormatInfo>,
}

impl CameraIdentity {
    pub fn label(&self) -> String {
        format!("{} #{} [id: {}]", self.camera_name, self.camera_index, self.camera_id)
    }
}

/// Multi-camera synchronized payload with gatherer-level timestamps.
#[derive(Debug)]
pub struct MultiFramePayload {
    pub frames: Vec<FramePacket>,
    pub frame_number: i64,
    /// Stamped when the last camera's `recv()` completes.
    pub all_frames_received_ns: i64,
    /// Stamped after the `MultiFramePayload` struct is assembled.
    pub payload_assembled_ns: i64,
    /// Stamped just before `multi_frame_sender.send()`.
    pub pre_send_downstream_ns: i64,
}

impl MultiFramePayload {
    /// Hardware synchronization spread: max - min of `frame_available_ns`
    /// across cameras in this multiframe.
    ///
    /// Measures the end-to-end physical variability of when each camera
    /// delivered its frame — sensor exposure timing + USB bus scheduling +
    /// driver buffering + decode. This is bounded by roughly one frame
    /// period (33ms at 30fps) because all threads start waiting after the
    /// same barrier release. In the typical case, we expect the spread to 
    /// be roughly +/1 0.5*frame_duration. 
    pub fn hardware_sync_spread_ns(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let avail: Vec<i64> = self.frames.iter().map(|f| f.timestamps.frame_available_ns).collect();
        let min = *avail.iter().min().unwrap();
        let max = *avail.iter().max().unwrap();
        let spread = max - min;
        if self.frame_number < 5 {
            eprintln!(
                "  [SPREAD mf#{}] hardware_sync: raw_avail={:?}  min={min}  max={max}  spread={spread} ns = {:.1} µs",
                self.frame_number,
                avail,
                spread as f64 / 1000.0,
            );
        }
        spread
    }

    /// Post-barrier-to-capture spread: max - min of `post_barrier_to_capture_ns`
    /// across cameras in this multiframe.
    ///
    /// `post_barrier_to_capture_ns` is the time from the previous barrier
    /// release to the start of this frame's capture call. The spread measures
    /// pure OS thread scheduling jitter — how far apart in time the OS
    /// scheduler picks up each camera thread to begin its next capture cycle.
    /// In the capture-then-barrier synchronization model, this is the
    /// engineering quality metric for software-level sync: lower spread
    /// means the OS is waking the camera threads in tighter lockstep.
    /// USB-webcam hardware-arrival spread dominates total sync error;
    /// this metric isolates the software contribution.
    pub fn post_barrier_to_capture_spread_ns(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let pbtc: Vec<i64> = self.frames.iter().map(|f| f.timestamps.post_barrier_to_capture_ns).collect();
        let min = *pbtc.iter().min().unwrap();
        let max = *pbtc.iter().max().unwrap();
        let spread = max - min;
        if self.frame_number < 5 {
            eprintln!(
                "  [SPREAD mf#{}] software_sync: raw_pbtc={:?}  min={min}  max={max}  spread={spread} ns = {:.1} µs",
                self.frame_number,
                pbtc,
                spread as f64 / 1000.0,
            );
        }
        spread
    }
}

/// Per-camera capture configuration — the Rust equivalent of the Python
/// Per-camera capture configuration — the Rust equivalent of the Python
/// `CameraConfig`. Passed as a single object everywhere. `camera_id` is the
/// primary identifier (matches the Python-generated SHA-256 hex ID).
/// Adding a new setting only means adding one field here.
#[derive(Debug, Clone, serde::Serialize)]
pub struct CameraConfig {
    pub camera_id: String,
    pub camera_index: u32,
    pub width: u32,
    pub height: u32,
    pub exposure: i32,
    pub exposure_mode: String,
    pub framerate: f64,
    pub rotation: i32,
}

#[derive(Debug)]
pub enum CameraCommand {
    Shutdown,
    Configure { config: CameraConfig },
}

#[derive(Debug)]
pub enum CameraEvent {
    Error(String),
}

#[derive(Debug, Clone)]
pub struct CameraHandle {
    pub command_sender: mpsc::Sender<CameraCommand>,
    pub identity: CameraIdentity,
    pub config: CameraConfig,
}

impl CameraHandle {
    pub fn send_shutdown(&self) {
        let _ = self.command_sender.send(CameraCommand::Shutdown);
    }
}
