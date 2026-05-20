//! Camera handle — the public interface to a running camera device.
//!
//! A `Camera` is a handle that communicates with a persistent OS thread running
//! the openpnp-capture capture loop. The thread owns the COM context (which is
//! thread-affine) and persists for the device's entire lifetime. Config changes
//! are sent as commands and applied on the existing thread.
//!
//! # Example
//!
//! ```ignore
//! let identities = detect_cameras()?;
//! let camera = Camera::start(identities[0].clone(), config, barrier)?;
//! while let Ok(frame) = camera.try_recv_frame() {
//!     println!("frame {}", frame.frame_number);
//! }
//! camera.shutdown()?;
//! ```

use std::sync::atomic::AtomicBool;
use std::sync::mpsc;
use std::sync::Arc;
use std::thread::JoinHandle;

use crate::camera_group::sync_utils::BreakableBarrier;

use super::types::{CameraCommand, CameraConfig, CameraEvent, CameraIdentity, FramePacket};

/// A handle to a running camera device.
///
/// The actual camera work happens on a dedicated OS thread that owns the
/// thread-affine DirectShow COM context. This handle communicates with that
/// thread via channels.
///
/// Dropping a `Camera` without calling `shutdown()` will detach the thread
/// (it continues running until it encounters a channel error).
pub struct Camera {
    command_sender: mpsc::Sender<CameraCommand>,
    frame_receiver: Option<mpsc::Receiver<FramePacket>>,
    event_receiver: mpsc::Receiver<CameraEvent>,
    thread_handle: Option<JoinHandle<()>>,
    identity: CameraIdentity,
    config: std::sync::Mutex<CameraConfig>,
}

impl Camera {
    /// Create the COM context, open the hardware stream, apply settings, run
    /// stabilization, and spawn the persistent capture thread.
    ///
    /// Returns a handle to the running camera, or an error if hardware setup
    /// fails (before any thread is spawned).
    pub fn start(
        identity: CameraIdentity,
        config: CameraConfig,
        barrier: Arc<BreakableBarrier>,
        paused: Arc<AtomicBool>,
        start_frame_number: i64,
    ) -> anyhow::Result<Self> {
        let (command_sender, event_receiver, frame_receiver, thread_handle) =
            super::camera_thread::spawn(&identity, &config, barrier, paused, start_frame_number)?;

        Ok(Self {
            command_sender,
            frame_receiver: Some(frame_receiver),
            event_receiver,
            thread_handle: Some(thread_handle),
            identity,
            config: std::sync::Mutex::new(config),
        })
    }

    /// Apply new capture settings on the running camera.
    ///
    /// Sends a `Configure` command to the capture thread, which applies the
    /// settings on its existing COM context. Settings that can be changed
    /// on-the-fly (exposure) take effect immediately. Settings that require
    /// a stream restart (resolution, framerate) are noted but may not take
    /// full effect until the camera is restarted.
    ///
    /// Takes `&self` (not `&mut self`) because sending a channel message
    /// only requires a shared reference. Updates the local config copy so
    /// that `config()` and `camera_statuses()` reflect the current settings.
    pub fn configure(&self, config: CameraConfig) {
        if let Ok(mut guard) = self.config.lock() {
            *guard = config.clone();
        }
        let _ = self
            .command_sender
            .send(CameraCommand::Configure { config });
    }

    /// Non-blocking frame poll.
    ///
    /// Returns the next available `FramePacket`, or `TryRecvError::Empty` if
    /// no frame is ready. The camera thread blocks on send when the channel
    /// is full (capacity 1), so each frame must be consumed before the next
    /// one is produced.
    pub fn try_recv_frame(&self) -> Result<FramePacket, mpsc::TryRecvError> {
        match &self.frame_receiver {
            Some(rx) => rx.try_recv(),
            None => Err(mpsc::TryRecvError::Disconnected),
        }
    }

    /// Non-blocking event poll.
    ///
    /// Returns `CameraEvent::Error(msg)` if the capture thread encountered
    /// an error, or `TryRecvError::Empty` if no events are pending.
    pub fn try_recv_event(&self) -> Result<CameraEvent, mpsc::TryRecvError> {
        self.event_receiver.try_recv()
    }

    /// Send the shutdown signal and wait for the capture thread to finish.
    ///
    /// Consumes the camera. The thread releases the COM context and exits.
    /// Returns `Ok(())` if the thread joined cleanly, or `Err` with the
    /// panic message if the thread panicked.
    pub fn shutdown(mut self) -> Result<(), String> {
        let _ = self.command_sender.send(CameraCommand::Shutdown);
        match self.thread_handle.take().unwrap().join() {
            Ok(()) => Ok(()),
            Err(e) => Err(format!(
                "Camera thread panicked: {}",
                e.downcast_ref::<&str>()
                    .unwrap_or(&"unknown error")
            )),
        }
    }

    /// The camera's identity (name, formats, unique ID).
    pub fn identity(&self) -> &CameraIdentity {
        &self.identity
    }

    /// The camera's active configuration (cloned from the latest known state).
    pub fn config(&self) -> CameraConfig {
        self.config.lock().unwrap().clone()
    }

    /// The frame receiver, for use in select!/polling multiplexed with other cameras.
    ///
    /// Returns `None` after `take_frame_receiver()` has been called (i.e., when
    /// the receiver has been moved to a gatherer thread in group operation).
    pub fn frame_receiver(&self) -> Option<&mpsc::Receiver<FramePacket>> {
        self.frame_receiver.as_ref()
    }

    /// Take ownership of the frame receiver.
    ///
    /// After this call, `try_recv_frame()` returns `Disconnected` and
    /// `frame_receiver()` returns `None`. Used by `CameraGroup` to hand
    /// the receiver to the gatherer thread.
    ///
    /// # Panics
    ///
    /// Panics if called more than once.
    pub fn take_frame_receiver(&mut self) -> mpsc::Receiver<FramePacket> {
        self.frame_receiver
            .take()
            .expect("frame_receiver already taken — gatherer owns it")
    }
}

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::detect::detect_cameras;
    use std::time::Duration;

    /// Helper: read `n` frames from the camera, participating in the barrier
    /// after each frame so the camera thread can continue its cycle.
    ///
    /// Returns all collected frames. Times out after `timeout` per frame.
    fn collect_frames(
        camera: &Camera,
        barrier: &BreakableBarrier,
        n: usize,
        _frame_timeout: Duration,
    ) -> Vec<FramePacket> {
        let mut frames = Vec::with_capacity(n);
        let mut consecutive_empty = 0u32;
        let max_consecutive_empty = 100; // ~500ms at 5ms sleep

        while frames.len() < n {
            match camera.try_recv_frame() {
                Ok(frame) => {
                    consecutive_empty = 0;
                    frames.push(frame);
                    barrier.wait();
                }
                Err(mpsc::TryRecvError::Empty) => {
                    consecutive_empty += 1;
                    if consecutive_empty > max_consecutive_empty {
                        tracing::warn!(
                            "collect_frames: timed out after {} empty polls (got {} of {} frames)",
                            consecutive_empty, frames.len(), n
                        );
                        break;
                    }
                    std::thread::sleep(Duration::from_millis(5));
                }
                Err(mpsc::TryRecvError::Disconnected) => {
                    tracing::warn!("collect_frames: channel disconnected");
                    break;
                }
            }
        }
        frames
    }

    fn make_config(identity: &CameraIdentity) -> CameraConfig {
        CameraConfig {
            camera_id: identity.camera_id.clone(),
            camera_index: identity.camera_index as u32,
            width: 1280,
            height: 720,
            exposure: -7,
            exposure_mode: "MANUAL".into(),
            framerate: 30.0,
            rotation: -1,
        }
    }

    // ── Hardware tests (require at least one camera attached) ──

    #[test]
    fn detect_cameras_finds_at_least_one() {
        let identities: Vec<CameraIdentity> = detect_cameras()
            .expect("detect_cameras failed")
            .into_iter()
            .map(|d| d.identity)
            .collect();
        assert!(
            !identities.is_empty(),
            "Expected at least one camera attached to the system"
        );
        for id in &identities {
            assert!(!id.camera_id.is_empty(), "camera_id must not be empty");
            assert!(!id.camera_name.is_empty(), "camera_name must not be empty");
            assert!(!id.formats.is_empty(), "must have at least one format");
        }
    }

    #[test]
    fn full_lifecycle_read_frames_and_framerate() {
        let identities: Vec<CameraIdentity> = detect_cameras()
            .expect("detect_cameras failed")
            .into_iter()
            .map(|d| d.identity)
            .collect();
        let identity = &identities[0];
        let config = make_config(identity);

        let barrier = Arc::new(BreakableBarrier::new(2)); // camera + test gatherer
        let camera =
            Camera::start(identity.clone(), config.clone(), barrier.clone(), Arc::new(AtomicBool::new(false)), 0)
                .expect("Camera::start failed");

        let frame_count = 30;
        let frames = collect_frames(&camera, &barrier, frame_count, Duration::from_secs(10));

        assert!(
            frames.len() >= 10,
            "expected at least 10 frames, got {}",
            frames.len()
        );

        // ── Frame rate statistics ──
        let loop_starts: Vec<i64> = frames
            .iter()
            .map(|f| f.timestamps.loop_start_ns)
            .collect();

        let mut intervals_ns: Vec<f64> = Vec::new();
        for i in 1..loop_starts.len() {
            intervals_ns.push((loop_starts[i] - loop_starts[i - 1]) as f64);
        }

        let mean_interval_ns: f64 =
            intervals_ns.iter().sum::<f64>() / intervals_ns.len() as f64;
        let mean_fps = 1_000_000_000.0 / mean_interval_ns;

        let min_fps = 1_000_000_000.0
            / intervals_ns
                .iter()
                .cloned()
                .fold(f64::NEG_INFINITY, f64::max);
        let max_fps = 1_000_000_000.0
            / intervals_ns
                .iter()
                .cloned()
                .fold(f64::INFINITY, f64::min);

        tracing::info!(
            "FPS stats over {} frames: mean={mean_fps:.1}  min={min_fps:.1}  max={max_fps:.1}",
            frames.len(),
        );

        assert!(
            mean_fps > 5.0 && mean_fps < 120.0,
            "mean FPS {mean_fps:.1} out of reasonable range (5-120)"
        );

        // ── Frame data validity ──
        for frame in &frames {
            assert!(frame.data.len() > 0, "frame data must not be empty");
            assert_eq!(frame.width, config.width);
            assert_eq!(frame.height, config.height);
            // MJPEG frames should start with JPEG SOI marker
            let bytes = frame.data.as_bytes();
            assert!(
                bytes.len() >= 2 && bytes[0] == 0xFF && bytes[1] == 0xD8,
                "MJPEG frame must start with JPEG SOI marker (0xFF 0xD8), got {:02X?}",
                &bytes[..bytes.len().min(4)]
            );
        }

        // ── Image statistics ──
        let sizes: Vec<usize> = frames.iter().map(|f| f.data.len()).collect();
        let mean_size = sizes.iter().sum::<usize>() as f64 / sizes.len() as f64;
        let min_size = sizes.iter().min().unwrap();
        let max_size = sizes.iter().max().unwrap();
        tracing::info!(
            "JPEG size stats: mean={mean_size:.0}B  min={min_size}B  max={max_size}B"
        );
        assert!(
            mean_size > 1000.0,
            "mean JPEG size too small ({mean_size:.0}B), probably not real image data"
        );

        // ── Timestamp monotonicity ──
        for i in 1..frames.len() {
            assert!(
                frames[i].timestamps.loop_start_ns > frames[i - 1].timestamps.loop_start_ns,
                "loop_start_ns must be monotonically increasing"
            );
            assert!(
                frames[i].frame_number > frames[i - 1].frame_number,
                "frame_number must be monotonically increasing"
            );
        }

        // ── Clean shutdown ──
        barrier.break_barrier();
        match camera.shutdown() {
            Ok(()) => tracing::info!("shutdown: clean"),
            Err(e) => tracing::warn!("shutdown: {e} (thread may have already exited)"),
        }
    }

    #[test]
    fn configure_mid_stream_changes_exposure() {
        let identities: Vec<CameraIdentity> = detect_cameras()
            .expect("detect_cameras failed")
            .into_iter()
            .map(|d| d.identity)
            .collect();
        let identity = &identities[0];
        let config = make_config(identity);

        let barrier = Arc::new(BreakableBarrier::new(2));
        let camera =
            Camera::start(identity.clone(), config.clone(), barrier.clone(), Arc::new(AtomicBool::new(false)), 0)
                .expect("Camera::start failed");

        // Read first batch with original exposure
        let first_frames = collect_frames(&camera, &barrier, 15, Duration::from_secs(10));
        assert!(
            first_frames.len() >= 5,
            "expected at least 5 frames before configure, got {}",
            first_frames.len()
        );

        // Change exposure mid-stream
        let mut new_config = config.clone();
        new_config.exposure = -5;
        camera.configure(new_config.clone());
        tracing::info!(
            "configure: exposure {} -> {}",
            config.exposure, new_config.exposure
        );

        // Read second batch with new exposure
        let second_frames = collect_frames(&camera, &barrier, 15, Duration::from_secs(10));
        assert!(
            second_frames.len() >= 5,
            "expected at least 5 frames after configure, got {}",
            second_frames.len()
        );

        // Verify frames are still valid after configure
        for frame in second_frames.iter() {
            assert!(frame.data.len() > 0, "post-configure frame must not be empty");
            let bytes = frame.data.as_bytes();
            assert!(
                bytes.len() >= 2 && bytes[0] == 0xFF && bytes[1] == 0xD8,
                "post-configure frame must be valid JPEG"
            );
        }

        // Verify rotation from new config is reflected
        for frame in second_frames.iter() {
            assert_eq!(frame.rotation, new_config.rotation);
        }

        tracing::info!(
            "frames: {} before configure, {} after configure",
            first_frames.len(),
            second_frames.len()
        );

        barrier.break_barrier();
        let _ = camera.shutdown();
    }

    #[test]
    fn frame_timestamps_are_populated() {
        let identities: Vec<CameraIdentity> = detect_cameras()
            .expect("detect_cameras failed")
            .into_iter()
            .map(|d| d.identity)
            .collect();
        let identity = &identities[0];
        let config = make_config(identity);

        let barrier = Arc::new(BreakableBarrier::new(2));
        let camera =
            Camera::start(identity.clone(), config, barrier.clone(), Arc::new(AtomicBool::new(false)), 0)
                .expect("Camera::start failed");

        let frames = collect_frames(&camera, &barrier, 5, Duration::from_secs(10));
        assert!(!frames.is_empty(), "expected at least 1 frame");

        for frame in &frames {
            let ts = &frame.timestamps;
            tracing::trace!(
                "frame {} timestamps: loop_start={}  frame_avail={}  post_jpeg_extract={}  pre_send={}  gatherer_recv={}",
                frame.frame_number,
                ts.loop_start_ns,
                ts.frame_available_ns,
                ts.post_jpeg_extract_ns,
                ts.pre_send_ns,
                ts.gatherer_received_ns,
            );

            // Every timestamp in the packet must belong to a single iteration.
            // (pre_barrier_ns and post_barrier_ns were removed because they
            // could only carry the previous iteration's values — see the note
            // in camera/types.rs.)
            assert!(ts.loop_start_ns > 0, "loop_start_ns not stamped");
            assert!(ts.frame_available_ns > 0, "frame_available_ns not stamped");
            assert!(ts.post_jpeg_extract_ns > 0, "post_jpeg_extract_ns not stamped");
            assert!(ts.pre_send_ns > 0, "pre_send_ns not stamped");

            // Causality within the current iteration.
            assert!(
                ts.loop_start_ns <= ts.frame_available_ns,
                "loop_start must precede frame_available"
            );
            assert!(
                ts.frame_available_ns <= ts.post_jpeg_extract_ns,
                "frame_available must precede post_jpeg_extract"
            );
            assert!(
                ts.post_jpeg_extract_ns <= ts.pre_send_ns,
                "post_jpeg_extract must precede pre_send"
            );
        }

        barrier.break_barrier();
        let _ = camera.shutdown();
    }

    #[test]
    fn identity_and_config_accessors() {
        let identities: Vec<CameraIdentity> = detect_cameras()
            .expect("detect_cameras failed")
            .into_iter()
            .map(|d| d.identity)
            .collect();
        let identity = &identities[0];
        let config = make_config(identity);

        let barrier = Arc::new(BreakableBarrier::new(2));
        let camera =
            Camera::start(identity.clone(), config.clone(), barrier.clone(), Arc::new(AtomicBool::new(false)), 0)
                .expect("Camera::start failed");

        assert_eq!(camera.identity().camera_id, identity.camera_id);
        assert_eq!(camera.config().width, config.width);
        assert_eq!(camera.config().height, config.height);
        assert_eq!(camera.config().exposure, config.exposure);

        barrier.break_barrier();
        let _ = camera.shutdown();
    }
}
