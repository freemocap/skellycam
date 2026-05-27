//! Camera channel protocol types.

use std::sync::mpsc;

/// All nanosecond-precision monotonic timestamps in a single frame's lifecycle.
///
/// The camera thread stamps fields as the frame moves through the capture loop.
/// The gatherer stamps `gatherer_received_ns` after `recv()` returns.
/// All values are nanoseconds since T=0 — the moment `init_logging()` was
/// called for this process (see `timestamps::performance::anchor_performance_clock`).
/// Zero means "not yet stamped."
#[derive(Debug, Clone)]
pub struct FrameLifecycleTimestamps {
    /// Top of the per-camera capture-loop iteration for this frame. For the
    /// first frame this is the moment the FSM was constructed (after camera
    /// stabilization completed). For every subsequent frame it equals the
    /// `post_barrier_ns` of the previous iteration.
    pub loop_start_ns: i64,
    /// `Cap_hasNewFrame()` returned true — the openpnp-capture device buffer
    /// has a frame ready for us to copy out.
    pub frame_available_ns: i64,
    /// `Cap_captureFrameRaw()` returned AND the raw MJPEG bytes have been
    /// copied into a heap-owned `Vec<u8>`. The interval
    /// `post_jpeg_extract_ns - frame_available_ns` is the JPEG-extract
    /// duration: the scientifically load-bearing metric that quantifies how
    /// much faster the raw-MJPEG path is than OpenCV's bundled
    /// `VideoCapture::read()` (which couples this byte-copy with a full
    /// JPEG decode into RGB).
    pub post_jpeg_extract_ns: i64,
    /// About to call `frame_sender.send(packet)`. Stamped immediately before
    /// the send so `gatherer_received_ns - pre_send_ns` measures end-to-end
    /// channel-send latency from the camera's point of view.
    pub pre_send_ns: i64,
    /// Stamped by the gatherer (not the camera) when `recv()` returns this
    /// frame's `FramePacket`.
    pub gatherer_received_ns: i64,
}

impl FrameLifecycleTimestamps {
    pub fn new() -> Self {
        Self {
            loop_start_ns: 0,
            frame_available_ns: 0,
            post_jpeg_extract_ns: 0,
            pre_send_ns: 0,
            gatherer_received_ns: 0,
        }
    }
}

// NOTE on per-camera barrier-wait:
//   Camera threads must call `barrier.wait()` AFTER sending their frame
//   downstream (the barrier is what synchronizes everyone for the next
//   iteration). That ordering means the timestamps bracketing
//   `barrier.wait()` happen AFTER the packet has already left the camera
//   thread — so they cannot be carried in this frame's `FramePacket`.
//   Carrying the PREVIOUS iteration's barrier timestamps and labeling them
//   as this iteration's was the source of an off-by-one attribution bug
//   that mixed data from two iterations in a single packet. To keep every
//   field in `FrameLifecycleTimestamps` honest about belonging to a single
//   iteration, those fields have been removed entirely. Per-camera
//   barrier-wait can be inferred from `cycle_total - (wait_for_frame +
//   jpeg_extract + channel_send_wait)`; the gatherer's OWN barrier wait is
//   still measured directly (one-iteration scope, no off-by-one).

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

/// Result of detecting a single camera — identity plus availability probe.
///
/// `available` is true when `Cap_isDeviceAvailable` returned `CAPRESULT_OK`,
/// meaning the camera is likely free to open. This is a fast, non-invasive
/// Tier 1 check — it does not power on the sensor. The Tier 2 definitive
/// check happens at `Cap_openStream` time.
#[derive(Debug, Clone)]
pub struct CameraDetection {
    pub identity: CameraIdentity,
    pub available: bool,
}

/// Gatherer-level timestamps for one multiframe cycle.
///
/// Populated by the gatherer state machine. One set per multiframe.
#[derive(Debug, Clone, Copy)]
pub struct GathererTimestamps {
    /// Start of this gatherer iteration.
    pub collecting_start_ns: i64,
    /// When the last camera's `FramePacket` is received.
    pub all_frames_received_ns: i64,
    /// When the gatherer exits `barrier.wait()`.
    pub post_barrier_ns: i64,
    /// After the `MultiFramePayload` struct is assembled.
    pub payload_assembled_ns: i64,
    /// Just before `multi_frame_sender.send(payload)`.
    pub pre_send_downstream_ns: i64,
}

impl GathererTimestamps {
    pub fn new() -> Self {
        Self {
            collecting_start_ns: 0,
            all_frames_received_ns: 0,
            post_barrier_ns: 0,
            payload_assembled_ns: 0,
            pre_send_downstream_ns: 0,
        }
    }
}

impl Default for GathererTimestamps {
    fn default() -> Self { Self::new() }
}

/// Multi-camera synchronized payload with gatherer-level timestamps.
#[derive(Debug)]
pub struct MultiFramePayload {
    pub frames: Vec<FramePacket>,
    pub frame_number: i64,
    /// Per-cycle gatherer timestamps (replaces bare i64 fields).
    pub gatherer_timestamps: GathererTimestamps,
}

impl MultiFramePayload {
    /// Frame arrival spread: max - min of `frame_available_ns` across cameras
    /// in this multiframe.
    ///
    /// Measures the wall-clock variability of when each camera's frame
    /// appeared in our software. Dominated by USB bus scheduling order,
    /// driver buffering, and the cameras' independent exposure clocks — no
    /// USB webcam guarantees lockstep frame delivery. The practical floor on
    /// consumer UVC webcams is up to one frame period (~33 ms at 30 fps).
    pub fn frame_arrival_spread_ns(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let avail: Vec<i64> = self
            .frames
            .iter()
            .map(|f| f.timestamps.frame_available_ns)
            .collect();
        let min = *avail.iter().min().unwrap();
        let max = *avail.iter().max().unwrap();
        max - min
    }

    /// Thread wakeup spread: max - min of `loop_start_ns` across cameras.
    ///
    /// `loop_start_ns` is stamped immediately after each camera thread exits
    /// the shared barrier. Because every camera exits the SAME barrier, this
    /// spread isolates pure OS thread scheduling jitter — how evenly the OS
    /// scheduler wakes the N camera threads after the synchronized release.
    /// Expected: microseconds. Milliseconds here means CPU contention,
    /// thread-priority misconfiguration, or a busy CPU core.
    pub fn thread_wakeup_spread_ns(&self) -> i64 {
        if self.frames.len() < 2 {
            return 0;
        }
        let starts: Vec<i64> = self
            .frames
            .iter()
            .map(|f| f.timestamps.loop_start_ns)
            .collect();
        let min = *starts.iter().min().unwrap();
        let max = *starts.iter().max().unwrap();
        max - min
    }
}

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
    /// Sent after stabilization completes — the camera is in its capture loop.
    Ready,
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
