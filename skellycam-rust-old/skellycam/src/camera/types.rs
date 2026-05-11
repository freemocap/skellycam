//! Camera data types: the channel protocol between camera thread,
//! decoder thread, gatherer, and main thread.
//!
//! ## Channel topology (multi-camera with structural backpressure)
//!
//! ```text
//! camera 0 ──RawFrame──→ decoder 0 ──FramePacket──→ gatherer
//! camera 1 ──RawFrame──→ decoder 1 ──FramePacket──→ gatherer
//!                                                      │
//!                                              MultiFramePayload
//!                                                      ↓
//!                                                 main thread
//! ```
//!
//! Each camera has its own dedicated thread + decoder thread pair.
//! The gatherer calls `recv()` on every decoder channel in sequence —
//! this IS the synchronization.  No camera can advance to frame N+1
//! until the gatherer has consumed frame N from all cameras, creating
//! structural lockstep through backpressure.

use std::sync::mpsc;

// ── Raw frame (camera thread → decoder thread) ──────────────────────

/// Raw encoded frame straight from the camera sensor.
/// The camera thread grabs this and immediately sends it to the decoder —
/// no decoding happens on the camera thread, keeping it as thin as possible.
#[derive(Debug, Clone)]
pub struct RawFrame {
    /// Raw encoded bytes (typically MJPEG, sometimes YUYV or NV12).
    pub raw_bytes: Vec<u8>,
    /// Monotonic timestamp (nanoseconds) captured right after `camera.frame()` returned.
    pub grab_timestamp_nanoseconds: i64,
    /// Three-part camera identity (name, index, unique ID).
    pub identity: CameraIdentity,
    /// Absolute frame number, monotonically increasing, starting from 0.
    pub frame_number: i64,
}

// ── Decoded frame (decoder thread → main thread) ────────────────────

/// The pixel data carried by a FramePacket.
/// Backends choose the format: nokhwa sends JPEG bytes (passthrough),
/// opencv sends BGR pixels (already decoded by capture.read()).
#[derive(Debug, Clone)]
pub enum FrameData {
    /// JPEG-encoded bytes (~100KB for 720p) — nokhwa passthrough.
    Jpeg(Vec<u8>),
    /// Raw BGR pixel data, row-major, 3 bytes per pixel — opencv backend.
    Bgr(Vec<u8>),
}

impl FrameData {
    /// Length of the underlying byte buffer.
    pub fn len(&self) -> usize {
        match self {
            Self::Jpeg(bytes) => bytes.len(),
            Self::Bgr(bytes) => bytes.len(),
        }
    }
}

/// A single camera frame traveling through the pipeline.
#[derive(Debug, Clone)]
pub struct FramePacket {
    /// Frame pixel data — either JPEG or BGR depending on backend.
    pub data: FrameData,
    /// Image width in pixels.
    pub width: u32,
    /// Image height in pixels.
    pub height: u32,
    /// Monotonic timestamp (ns) from the original camera grab.
    pub grab_timestamp_nanoseconds: i64,
    /// Three-part camera identity (name, index, unique ID).
    pub identity: CameraIdentity,
    /// Absolute frame number for multi-camera synchronization.
    pub frame_number: i64,
}

// ── Multi-frame payload (gatherer → main thread) ────────────────────

/// A synchronized set of frames, one from each camera at the same step.
/// The gatherer assembles this after receiving from all decoder channels.
#[derive(Debug)]
pub struct MultiFramePayload {
    /// One FramePacket per camera, all at the same synchronization step.
    pub frames: Vec<FramePacket>,
    /// Absolute multi-frame step number, monotonically increasing from 0.
    pub step: i64,
}

impl MultiFramePayload {
    /// The range (max - min) of grab timestamps across all cameras,
    /// in nanoseconds.  This is the inter-camera synchronization spread —
    /// smaller is better.
    pub fn inter_camera_grab_spread_nanoseconds(&self) -> i64 {
        if self.frames.is_empty() {
            return 0;
        }
        let minimum = self
            .frames
            .iter()
            .map(|frame| frame.grab_timestamp_nanoseconds)
            .min()
            .unwrap();
        let maximum = self
            .frames
            .iter()
            .map(|frame| frame.grab_timestamp_nanoseconds)
            .max()
            .unwrap();
        maximum - minimum
    }
}

// ── Camera identity ──────────────────────────────────────────────────

/// Three-part camera identification, from least to most specific.
///
/// - `display_name`: human-readable, not unique (e.g. "USB Camera")
/// - `camera_index`: ordinal position in the system's device list
/// - `unique_identifier`: platform-specific stable ID from `CameraInfo::misc()`,
///   hashed to a short hex string for readability while retaining uniqueness
#[derive(Debug, Clone)]
pub struct CameraIdentity {
    /// Human-readable camera model name (e.g. "Logi C310 HD WebCam").
    pub display_name: String,
    /// Ordinal position in the system camera list (0, 1, 2...).
    pub camera_index: i32,
    /// Short unique hex ID derived from the platform-specific device path.
    /// Stable across replug and reboot (on Windows and macOS; best-effort on Linux).
    pub unique_identifier: String,
    /// The full platform-specific device path used to generate the identifier.
    /// Stored for debugging but not used in the protocol.
    pub device_path: String,
}

impl CameraIdentity {
    /// Formatted string combining the display name and unique ID for logging.
    pub fn label(&self) -> String {
        format!("{} [{}]", self.display_name, self.unique_identifier)
    }
}

// ── Command/event protocol (main thread ↔ camera thread) ────────────

/// Command sent from the main thread to a camera thread.
#[derive(Debug)]
pub enum CameraCommand {
    /// Stop capturing, close the camera, and exit the thread.
    Shutdown,
}

/// Event sent from a camera thread back to the main thread.
#[derive(Debug)]
pub enum CameraEvent {
    /// A non-fatal error from the camera thread.
    Error(String),
}

/// Handle to a running camera thread.
/// The main thread holds one of these to send commands.
#[derive(Debug, Clone)]
pub struct CameraHandle {
    pub command_sender: mpsc::Sender<CameraCommand>,
    pub identity: CameraIdentity,
    pub width: u32,
    pub height: u32,
}

impl CameraHandle {
    /// Send a shutdown command to the camera thread.
    pub fn send_shutdown(&self) {
        let _ = self.command_sender.send(CameraCommand::Shutdown);
    }
}
