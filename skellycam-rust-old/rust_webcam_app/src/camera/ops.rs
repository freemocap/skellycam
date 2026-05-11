//! Public camera operations: list, query, spawn.
//!
//! These free functions are the public API of the camera module.  They handle
//! camera enumeration, one-shot metadata queries, and thread spawning.
//!
//! ## Python analogy
//!
//! | Rust function | Python equivalent |
//! |--------------|-------------------|
//! | `list_cameras()` | `for i in range(10): cap = cv2.VideoCapture(i); if cap.isOpened(): print(...)` |
//! | `query_camera(idx)` | `cap = cv2.VideoCapture(idx); w = cap.get(CAP_PROP_FRAME_WIDTH); ...; cap.release()` |
//! | `spawn_camera_thread(idx)` | `threading.Thread(target=camera_loop, args=(idx,)).start()` |
//!
//! ## MPSC channels — the core concurrency primitive
//!
//! `mpsc` = **M**ultiple **P**roducer, **S**ingle **C**onsumer.  This is
//! Rust's equivalent of Python's `queue.Queue`:
//!
//! | Rust | Python |
//! |------|--------|
//! | `mpsc::channel()` | `queue.Queue()` (unbounded) |
//! | `mpsc::sync_channel(N)` | `queue.Queue(maxsize=N)` |
//! | `sender.send(msg)` | `q.put(msg)` |
//! | `receiver.recv()` | `q.get()` (blocking) |
//! | `receiver.try_recv()` | `q.get_nowait()` |
//!
//! Key difference: Rust channels are **typed** — a given channel transports
//! exactly one type.  `mpsc::Sender<CameraCommand>` can only send
//! `CameraCommand` values.  This means no `isinstance()` checks on received
//! messages — the type system guarantees correctness.

use std::sync::mpsc;
use std::thread;
use std::time::Instant;

use anyhow::{Context, Result};
use nokhwa::pixel_format::RgbFormat;
use nokhwa::utils::{
    ApiBackend, CameraIndex, CameraInfo, RequestedFormat, RequestedFormatType, Resolution,
};
use nokhwa::Camera;

use super::manager::CameraManager;
use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraMetadata, FramePacket};

// ── Public free functions ─────────────────────────────────────────────

/// List all available cameras, printing details to stdout.
///
/// Opens each camera briefly to query metadata, then closes it.  This is the
/// equivalent of `cv2.VideoCapture(i).isOpened()` for all plausible indices.
pub fn list_cameras() -> Result<Vec<CameraInfo>> {
    let cameras = nokhwa::query(ApiBackend::Auto)
        .context("Failed to query cameras — is a webcam connected?")?;
    if cameras.is_empty() {
        println!("No cameras found.");
    } else {
        println!("Found {} camera(s):\n", cameras.len());
        for (index, camera_info) in cameras.iter().enumerate() {
            println!("  Camera {index}: {}", camera_info.human_name());
            println!("    misc:    {}", camera_info.misc());
            println!();
        }
    }
    Ok(cameras)
}

/// Open a camera temporarily on the calling thread, read its metadata
/// (name, resolution, supported controls), then close it.
///
/// This is called **on the main thread** before spawning the camera thread,
/// so we know the camera's capabilities before the persistent stream starts.
///
/// ## Why the temporary open/close?
///
/// The camera thread needs metadata (resolution, supported controls) to set
/// up the display window and control UI.  Rather than querying these
/// asynchronously over channels, we do a quick open-query-close cycle on the
/// main thread.  This is safe because the camera is only briefly held — no
/// streaming loop competes for it.
///
/// Python analogy: this is like calling
/// ```python
/// cap = cv2.VideoCapture(idx)
/// w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
/// h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
/// cap.release()
/// ```
/// before starting a capture thread, so the UI knows the frame size upfront.
pub fn query_camera(index: u32, width: u32, height: u32) -> Result<CameraMetadata> {
    let cameras = nokhwa::query(ApiBackend::Auto)?;
    if cameras.is_empty() {
        anyhow::bail!("No cameras found.");
    }
    if index as usize >= cameras.len() {
        anyhow::bail!(
            "Camera index {index} is out of range (found {} camera(s)).",
            cameras.len()
        );
    }

    let camera_name = cameras[index as usize].human_name();

    let requested =
        RequestedFormat::new::<RgbFormat>(RequestedFormatType::AbsoluteHighestFrameRate);
    let mut camera = Camera::new(CameraIndex::Index(index), requested)
        .context("Failed to create camera handle — camera may be in use by another app.")?;

    if width > 0 && height > 0 {
        let resolution = Resolution::new(width, height);
        let _ = camera.set_resolution(resolution);
    }

    camera
        .open_stream()
        .context("Failed to start the camera stream (metadata query).")?;

    let resolution = camera.resolution();
    let (width, height) = (resolution.width(), resolution.height());

    let supported_controls = camera
        .supported_camera_controls()
        .context("Failed to query supported controls.")?;

    // `stop_stream()` is called by Drop, but be explicit.
    camera.stop_stream()?;

    Ok(CameraMetadata {
        camera_name,
        resolution: (width, height),
        supported_controls,
    })
}

/// Spawn a camera thread and return a handle for sending commands plus the
/// receiver end of the event channel.
///
/// The camera is opened **on the spawned thread** so that platform-specific
/// initialisation (COM STA on Windows, AVFoundation session on macOS, V4L2
/// on Linux) happens where the camera lives.  The camera never crosses a
/// thread boundary — only `RgbImage` (owned `Vec<u8>`) and primitive types
/// travel across the channels.
///
/// ## Channel configuration
///
/// - **command channel**: unbounded `mpsc::channel()`.  Commands are small and
///   infrequent, so an unbounded buffer is fine.
/// - **event channel**: `mpsc::sync_channel(2)` — bounded to 2 frames.  This
///   provides **backpressure**: if the main thread falls behind, the camera
///   thread blocks on `send()` rather than queuing unbounded frames in memory.
///   2 is the minimum that allows one frame in transit while the camera thread
///   captures the next.  Think of it like `queue.Queue(maxsize=2)`.
///
/// ## The camera thread's main loop
///
/// Each iteration has two phases:
///
/// **Phase A — drain commands** (non-blocking via `try_recv()`):
/// Process all pending `CameraCommand`s so the main thread never waits for
/// control adjustments.  Continues until the command queue is empty.
///
/// **Phase B — capture next frame**:
/// Grab a frame, wrap it in a `FramePacket` with a sequence number and
/// timestamp, and send it to the main thread through the sync channel.
/// If the receiver is full (main thread is slow), this call blocks — that's
/// the backpressure mechanism.
///
/// ## Why `move` on the closure?
///
/// `thread::spawn(move || { ... })` — the `move` keyword tells Rust to
/// **capture ownership** of all variables the closure references.  Without
/// `move`, the closure would borrow references, and the compiler would
/// complain that those references might outlive the stack frame.  This is
/// unique to Rust — Python closures always capture by reference.
///
/// ## Rust shutdown pattern
///
/// The camera thread shuts down when:
/// 1. Main thread sends `CameraCommand::Shutdown`.
/// 2. Main thread drops the `command_sender`, causing `try_recv()` to return
///    `Disconnected`.
/// 3. Main thread drops the `event_receiver`, causing `send()` on a frame to
///    fail (main has exited without explicit shutdown).
///
/// In all cases, `camera_manager.close()` stops the stream and the thread
/// exits cleanly.
pub fn spawn_camera_thread(
    index: u32,
    width: u32,
    height: u32,
    _frames_per_second: u32,
    camera_id: u32,
    metadata: CameraMetadata,
) -> (CameraHandle, mpsc::Receiver<CameraEvent>) {
    let (command_sender, command_receiver) = mpsc::channel::<CameraCommand>();
    let (event_sender, event_receiver) = mpsc::sync_channel::<CameraEvent>(2);

    let handle = CameraHandle {
        command_sender: command_sender.clone(),
        camera_id,
        metadata,
    };

    thread::spawn(move || {
        // ── Open camera ON THIS THREAD ────────────────────────────
        let mut camera_manager = match CameraManager::open_inner(index, width, height) {
            Ok(mgr) => mgr,
            Err(error) => {
                let _ = event_sender.send(CameraEvent::Error(format!(
                    "Failed to open camera: {error}"
                )));
                return;
            }
        };

        println!("Opened: {}", camera_manager.camera_name);
        println!(
            "Streaming at {}x{}",
            camera_manager.width, camera_manager.height
        );

        let mut sequence: u64 = 0;

        loop {
            // ── Phase A: drain all pending commands (non-blocking) ──
            let mut should_shutdown = false;
            loop {
                match command_receiver.try_recv() {
                    Ok(CameraCommand::Shutdown) => {
                        should_shutdown = true;
                        break;
                    }
                    Ok(CameraCommand::AdjustControl(control, delta)) => {
                        let result = camera_manager
                            .adjust_control(control, delta)
                            .map_err(|error| error.to_string());
                        let _ = event_sender.send(CameraEvent::ControlAdjusted(result));
                    }
                    Ok(CameraCommand::GetControlInfo(control)) => {
                        let result = camera_manager
                            .get_control_info(control)
                            .map(|(value, description)| (value, format!("{description:?}")))
                            .map_err(|error| error.to_string());
                        let _ = event_sender.send(CameraEvent::ControlInfo(result));
                    }
                    Err(mpsc::TryRecvError::Empty) => break,
                    Err(mpsc::TryRecvError::Disconnected) => {
                        should_shutdown = true;
                        break;
                    }
                }
            }
            if should_shutdown {
                let _ = camera_manager.close();
                return;
            }

            // ── Phase B: capture next frame ────────────────────────
            match camera_manager.capture() {
                Ok(frame) => {
                    let packet = FramePacket {
                        image: frame,
                        sequence,
                        timestamp: Instant::now(),
                        camera_id,
                    };
                    sequence += 1;
                    if event_sender.send(CameraEvent::Frame(packet)).is_err() {
                        // Main thread dropped receiver — shut down.
                        let _ = camera_manager.close();
                        return;
                    }
                }
                Err(error) => {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Capture error: {error}"
                    )));
                    // Don't exit on a single capture error; retry next iteration.
                }
            }
        }
    });

    (handle, event_receiver)
}
