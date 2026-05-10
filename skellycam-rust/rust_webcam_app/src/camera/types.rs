//! Channel protocol types: enums sent between main thread and camera thread.
//!
//! ## Rust concept: enums with data (tagged unions)
//!
//! In Python, if you wanted to send different kinds of messages over a queue,
//! you might use a dict with a `"type"` key:
//! ```python
//! {"type": "frame", "image": ..., "seq": 0}
//! {"type": "error", "msg": "camera lost"}
//! ```
//!
//! Rust enums encode this pattern directly in the type system.  Each variant
//! can carry different data, and the compiler checks that all match arms
//! handle every possible variant.  This is exhaustive pattern matching —
//! missing a variant is a compile error, not a runtime bug.
//!
//! ## Result<T, E> — Rust's try/except
//!
//! `Result<T, E>` is an enum:
//! ```rust,ignore
//! enum Result<T, E> { Ok(T), Err(E) }
//! ```
//!
//! The `?` operator is like `try:` in Python but explicit at the call site:
//! if the result is `Err`, it returns early; if it's `Ok`, it unwraps the value.
//!
//! When we send results across the channel, we use `Result<T, String>` — the
//! error is a string rather than an `anyhow::Error` because channel messages
//! need to implement `Debug`, and `anyhow::Error` doesn't.

use std::sync::mpsc;
use std::time::Instant;

use image::RgbImage;
use nokhwa::utils::KnownCameraControl;

// ── Channel protocol types ────────────────────────────────────────────

/// Command sent from the main thread to a camera thread.
///
/// Each variant represents one thing the main thread can ask the camera
/// thread to do.  Think of this as the "request" side of a request/response
/// protocol over channels.
#[derive(Debug)]
pub enum CameraCommand {
    /// Adjust a camera control by `delta` steps (positive = increase).
    AdjustControl(KnownCameraControl, i64),
    /// Query the current value and description of a camera control.
    GetControlInfo(KnownCameraControl),
    /// Stop capturing, close the camera, and exit the thread.
    Shutdown,
}

/// Event sent from a camera thread back to the main thread.
///
/// This is the "response" or "notification" side of the protocol.  Responses
/// to commands (`ControlAdjusted`, `ControlInfo`) carry `Result<T, String>`
/// because the camera thread can't use `anyhow::Error` across a channel boundary
/// (it doesn't implement `Debug` for channel transport).
#[derive(Debug)]
pub enum CameraEvent {
    /// A captured frame, ready for processing on the main thread.
    Frame(FramePacket),
    /// Result of an AdjustControl command.
    ControlAdjusted(Result<i64, String>),
    /// Result of a GetControlInfo command: (value, description_string).
    ControlInfo(Result<(i64, String), String>),
    /// A non-fatal error from the camera thread.
    Error(String),
}

/// A decoded frame with metadata for synchronisation.
///
/// `#[allow(dead_code)]` suppresses the compiler warning about fields that
/// aren't read yet (like `timestamp` and `camera_id`).  These are reserved
/// for future multi-camera timestamp alignment — analogous to storing a
/// Python `time.perf_counter()` alongside each frame for later sync.
#[derive(Debug)]
#[allow(dead_code)]
pub struct FramePacket {
    /// The decoded RGB image.  Owned and `Send` — ownership transfers
    /// from the camera thread to the main thread through the channel.
    pub image: RgbImage,
    /// Monotonically increasing frame number, starting from 0.
    /// Like `enumerate()` over a frame iterator in Python.
    pub sequence: u64,
    /// Wall-clock timestamp of capture on the camera thread.
    /// `Instant` is like `time.perf_counter()` — monotonic, high-res,
    /// not tied to wall-clock date/time.
    pub timestamp: Instant,
    /// Camera identifier (0 for single-camera; disambiguates multi-camera).
    pub camera_id: u32,
}

/// Information gathered from a temporary camera open on the main thread.
///
/// We open the camera briefly to query its name, actual resolution, and
/// supported controls, then close it before spawning the persistent camera
/// thread.  This avoids having to send control queries asynchronously during
/// startup.
///
/// Python analogy: `cv2.VideoCapture(0)` → `.get(cv2.CAP_PROP_FRAME_WIDTH)`
/// etc., but we do this on the main thread so we know the resolution before
/// the camera thread starts streaming.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct CameraMetadata {
    pub camera_name: String,
    /// (width, height) as discovered from the camera
    pub resolution: (u32, u32),
    /// Which controls (brightness, exposure, etc.) the camera supports
    pub supported_controls: Vec<KnownCameraControl>,
}

/// Handle to a running camera thread.
///
/// The main thread holds one of these to send commands.  The handle is cheap
/// to clone because `mpsc::Sender` is `Clone` — all clones share the same
/// channel.  (In Python, you'd pass the same `queue.Queue` reference around.)
///
/// ## Why `pub(crate)` on `command_sender`?
///
/// The field is crate-public so `controls.rs` functions can call
/// `camera_handle.send_adjust_control(...)` via the methods below.  External
/// crates cannot see it.
#[allow(dead_code)]
pub struct CameraHandle {
    pub(crate) command_sender: mpsc::Sender<CameraCommand>,
    pub camera_id: u32,
    pub metadata: CameraMetadata,
}

impl CameraHandle {
    /// Send an `AdjustControl` command to the camera thread.
    ///
    /// `let _ =` discards the `Result<(), SendError>` — if the camera thread
    /// has already exited, the send fails silently.  This is fine because the
    /// main loop will detect the channel closure on its next receive.
    pub fn send_adjust_control(&self, control: KnownCameraControl, delta: i64) {
        let _ = self
            .command_sender
            .send(CameraCommand::AdjustControl(control, delta));
    }

    /// Send a `GetControlInfo` command to the camera thread.
    pub fn send_get_control_info(&self, control: KnownCameraControl) {
        let _ = self
            .command_sender
            .send(CameraCommand::GetControlInfo(control));
    }

    /// Send a `Shutdown` command to the camera thread.
    pub fn send_shutdown(&self) {
        let _ = self.command_sender.send(CameraCommand::Shutdown);
    }
}
