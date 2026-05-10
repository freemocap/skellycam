//! Main-loop orchestration.
//!
//! This is the heart of the application — the single-threaded frame processing
//! loop that ties together all the modules.  Every frame goes through these
//! stages in order:
//!
//! ```text
//! Keyboard → Receive Frame → Rotate → Scale → Recreate Window?
//! → Feed Recorder → Draw Overlay → RGB→ARGB → Update Display Buffer
//! ```
//!
//! Each stage is individually timed and the averages are printed periodically.
//!
//! ## Architecture: why one main thread?
//!
//! The camera has its own thread, but all frame **processing** happens on the
//! main thread.  This is deliberate:
//!
//! 1. **Simplicity**: No locks, no atomics, no shared mutable state.  The
//!    camera thread sends owned frames through a channel, and the main thread
//!    receives and processes them sequentially.
//!
//! 2. **Platform requirement**: `minifb` windows must be created and updated
//!    on the main thread on macOS and some Linux window managers.
//!
//! 3. **Predictable latency**: With a single consumer, frame processing order
//!    is deterministic.  No pipeline interleaving to reason about.
//!
//! For multi-camera setups, each camera gets its own thread, but a single
//! consumer thread gathers frames (with timestamps for alignment) and handles
//! display — analogous to a fan-in topology.
//!
//! ## Python / OpenCV analogy
//!
//! ```python
//! import cv2
//! import time
//! from collections import deque
//!
//! cap = cv2.VideoCapture(0)
//! frame_times = deque(maxlen=30)
//!
//! while True:
//!     loop_start = time.perf_counter()
//!
//!     # Keyboard
//!     key = cv2.waitKey(1) & 0xFF
//!     if key == ord('q'):
//!         break
//!
//!     # Receive frame (OpenCV combines capture + decode)
//!     ret, frame = cap.read()
//!     if not ret:
//!         break
//!
//!     # Rotate
//!     t0 = time.perf_counter()
//!     frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
//!     rotate_time = time.perf_counter() - t0
//!
//!     # Display (with timing)
//!     cv2.imshow("Webcam", frame)
//!
//!     # FPS tracking
//!     frame_times.append(time.perf_counter() - loop_start)
//!     fps = len(frame_times) / sum(frame_times)
//! ```
//!
//! The Rust version does the same thing, but:
//! - Frame capture is decoupled from processing (separate thread).
//! - Per-stage timing is tracked separately (the Python version above lumps
//!   all processing into one loop iteration).
//! - The overlay is drawn on the pixel buffer, not with `cv2.putText`.
//! - Rotation uses the `image` crate instead of OpenCV.
//!
//! ## Rust concepts used
//!
//! - **`VecDeque`** is `collections.deque` — a double-ended queue with O(1)
//!   push/pop at both ends.  Used here for a rolling FPS window.
//! - **`Instant::now()`** is `time.perf_counter()` — monotonic, high-resolution,
//!   not affected by system clock adjustments.
//! - **`match` on `Result` and enum variants** replaces Python's `try/except`
//!   and `isinstance()` chains.  The compiler checks exhaustiveness.
//! - **`if let Some(ref mut x) = opt`** is a pattern-match that borrows the
//!   inner value mutably — like `if opt is not None: x = opt` in Python but
//!   with ownership tracking.

use std::collections::VecDeque;
use std::time::Instant;

use anyhow::Result;

use crate::camera::{self, CameraEvent};
use crate::cli::Arguments;
use crate::controls::{self, CONTROLS};
use crate::display::{draw_overlay, DisplayWindow, OverlayState};
use crate::pipeline;
use crate::recorder::VideoRecorder;
use crate::timing;

// ── main loop orchestration ───────────────────────────────────────────

/// Run the application: query camera metadata, open the display window,
/// spawn the camera thread, and enter the main frame-processing loop.
///
/// ## Startup sequence
///
/// 1. If `--list`, print camera info and exit.
/// 2. **Query camera metadata** on the main thread (temporary open/close).
///    This gives us resolution and supported controls before the camera
///    thread starts.
/// 3. **Open display window** with the known resolution.
/// 4. **Spawn camera thread** — the camera opens and starts streaming on
///    its own thread.  Returns a `CameraHandle` (for sending commands) and
///    a `Receiver<CameraEvent>` (for receiving frames).
/// 5. **Enter main loop** — process one event per iteration until the window
///    closes or Q/Esc is pressed.
///
/// ## The main loop in detail
///
/// Each iteration processes exactly **one** `CameraEvent` from the channel.
/// This is the most common event-driven loop pattern in Rust GUI/capture apps.
///
/// The loop blocks on `event_receiver.recv()` — it waits for the next frame
/// or control response from the camera thread.  This means:
/// - Frame rate is determined by the camera's capture rate.
/// - The main thread sleeps between frames (no busy-waiting).
/// - Commands (keyboard-driven) are processed between frames by the camera
///   thread in its "drain commands" phase.
///
/// ## Keyboard handling
///
/// Keys are polled at the **start** of each iteration before `recv()`.  If
/// the user presses a key between frames, it's handled immediately.  If the
/// camera thread blocks (slow frame), keys still accumulate in minifb's
/// input queue.
///
/// Key mappings:
/// - `Q` / `Escape` — graceful shutdown
/// - `R` — toggle recording on/off
/// - `1`–`9` — select camera control (brightness, contrast, etc.)
/// - `↑` / `↓` — adjust selected control up/down
/// - `←` / `→` — rotate image 90° counterclockwise/clockwise
/// - `S` — print all current camera settings
///
/// ## Shutdown sequence
///
/// 1. Send `CameraCommand::Shutdown` to the camera thread.
/// 2. Drain any buffered `CameraEvent`s from the channel (`try_recv()` loop).
///    This is necessary because the camera thread may have sent frames that
///    are waiting in the bounded channel — without draining, the camera
///    thread would block on `send()` and never process the shutdown command.
/// 3. Call `finish()` on any active recorder.
/// 4. Return `Ok(())`.
///
/// ## Why drain buffered events before shutdown?
///
/// The event channel is `sync_channel(2)`.  If 2 frames are queued, the
/// camera thread's `send()` blocks.  We need to consume (and discard) those
/// frames so the camera thread can process the `Shutdown` command and exit.
/// This is like calling `queue.get_nowait()` in a loop until `Empty` in Python.
pub(crate) fn run(arguments: Arguments) -> Result<()> {
    if arguments.list {
        camera::list_cameras()?;
        return Ok(());
    }

    // --- query camera metadata (temp open on main thread) ---
    //
    // We open the camera briefly on the main thread to read its actual
    // resolution and supported controls.  This is safe because we close it
    // before spawning the camera thread that holds the persistent stream.
    let metadata = camera::query_camera(
        arguments.camera,
        arguments.width,
        arguments.height,
    )?;

    let camera_width = metadata.resolution.0;
    let camera_height = metadata.resolution.1;
    let supported_controls = metadata.supported_controls.clone();

    // --- print controls help ---
    controls::print_controls_help(&supported_controls);

    // --- open display window ---
    let window_title = "Webcam App — [q]uit [r]ecord [←→]rotate";
    let mut display = DisplayWindow::new(camera_width, camera_height, window_title)?;
    let mut recorder: Option<VideoRecorder> = None;

    // Rotation: 0=0°, 1=90°CW, 2=180°, 3=270°CW
    //
    // We track rotation as a `u8` (0–3) rather than an enum because it maps
    // neatly to `match` arms and `rem_euclid(4)` wrapping.
    let mut rotation: u8 = 0;

    // Current display dimensions — may differ from camera resolution after
    // rotation (90°/270° swap width/height) or scale-to-fit.
    let mut display_width = camera_width;
    let mut display_height = camera_height;

    // Control selection — index into the CONTROLS array (0 = Brightness, etc.)
    let mut selected_control_index: usize = 0;
    let mut current_control_value: i64 = 0;

    // FPS tracking via rolling 30-frame window.
    //
    // `VecDeque<f64>` stores the per-frame elapsed time in seconds.  FPS is
    // computed as `len / sum(durations)`, which gives the harmonic mean of
    // instantaneous frame rates and handles variable frame times smoothly.
    //
    // Python equivalent:
    // ```python
    // from collections import deque
    // frame_times = deque(maxlen=30)  # but we manage capacity manually
    // fps = len(frame_times) / sum(frame_times)
    // ```
    let mut frame_times: VecDeque<f64> = VecDeque::with_capacity(30);
    let mut frames_per_second = 0.0;

    // Per-stage timing accumulators (nanoseconds, reset every TIMING_INTERVAL frames).
    //
    // Each accumulator stores the **sum** of durations for one pipeline stage,
    // accumulated over `TIMING_INTERVAL` frames.  `timing::print_timing()` prints
    // the average (sum / interval_count) in microseconds, then resets to 0.
    //
    // `u128` is used because a `u64` of nanoseconds is ~18 seconds max —
    // 60 frames at 30 FPS (2 seconds) fits in `u64`, but `u128` gives
    // headroom for high-res timing at very low frame rates.
    let mut accumulated_keyboard_nanoseconds = 0u128;
    let mut accumulated_rotation_nanoseconds = 0u128;
    let mut accumulated_scale_nanoseconds = 0u128;
    let mut accumulated_dimension_update_nanoseconds = 0u128;
    let mut accumulated_record_nanoseconds = 0u128;
    let mut accumulated_conversion_nanoseconds = 0u128;
    let mut accumulated_buffer_update_nanoseconds = 0u128;
    let mut accumulated_total_nanoseconds = 0u128;
    let mut frame_index: u64 = 0;

    // --- spawn camera thread ---
    //
    // This returns immediately.  The camera thread starts and begins capturing
    // frames asynchronously.  `camera_handle` is used to send commands
    // (adjust control, shutdown).  `event_receiver` is where frames and
    // control responses arrive.
    //
    // Python equivalent:
    // ```python
    // event_queue = queue.Queue(maxsize=2)
    // thread = threading.Thread(target=camera_loop, args=(idx, event_queue))
    // thread.start()
    // ```
    let (camera_handle, event_receiver) = camera::spawn_camera_thread(
        arguments.camera,
        arguments.width,
        arguments.height,
        arguments.frames_per_second,
        0, // camera_id — single camera for now
        metadata,
    );

    // ── main loop ──────────────────────────────────────────────────
    //
    // The loop condition checks `display.is_open()` each iteration, which
    // returns false when the user clicks the window's close button.  This
    // plus the Q/Esc key handler are the two exit paths.
    while display.is_open() {
        let loop_start = Instant::now();

        // --- keyboard ---
        //
        // Poll keyboard at the start of each iteration.  We collect all
        // pending keys and iterate over them.  Most key presses send commands
        // through the camera handle (non-blocking — the camera thread
        // processes them in its own loop).
        //
        // `display.collect_keys()` returns `&[Key]` — a borrowed slice
        // into a Vec that lives in `display`.  We `.to_vec()` to take
        // ownership of the key list, releasing the borrow on `display`
        // so we can mutate it later (e.g., in `toggle_recording`).
        let keyboard_start = Instant::now();
        {
            let keys: Vec<minifb::Key> = display.collect_keys().to_vec();
            for key in keys {
                match key {
                    // ── Quit ──────────────────────────────────────
                    minifb::Key::Escape | minifb::Key::Q => {
                        // Graceful shutdown: tell the camera thread to stop,
                        // drain the event channel so the camera thread can
                        // unblock, then finish any active recording.
                        camera_handle.send_shutdown();
                        // Drain buffered events so the camera thread can unblock.
                        // CameraEvent includes Frame packets which carry owned
                        // RgbImages — dropping them here frees the memory.
                        while let Ok(event) = event_receiver.try_recv() {
                            let _ = event;
                        }
                        finish(recorder)?;
                        return Ok(());
                    }

                    // ── Toggle recording ─────────────────────────
                    minifb::Key::R => {
                        recorder = toggle_recording(
                            recorder,
                            &mut display,
                            display_width,
                            display_height,
                            arguments.frames_per_second,
                            &arguments.output,
                        )?;
                    }

                    // ── Select camera control (keys 1–9) ─────────
                    // Each key maps to an index in the CONTROLS array.
                    // The selected control's name is printed, and
                    // subsequent Up/Down presses adjust it.
                    minifb::Key::Key1 => {
                        selected_control_index = controls::select_control(
                            0,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key2 => {
                        selected_control_index = controls::select_control(
                            1,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key3 => {
                        selected_control_index = controls::select_control(
                            2,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key4 => {
                        selected_control_index = controls::select_control(
                            3,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key5 => {
                        selected_control_index = controls::select_control(
                            4,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key6 => {
                        selected_control_index = controls::select_control(
                            5,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key7 => {
                        selected_control_index = controls::select_control(
                            6,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key8 => {
                        selected_control_index = controls::select_control(
                            7,
                            &camera_handle.metadata.supported_controls,
                        );
                    }
                    minifb::Key::Key9 => {
                        selected_control_index = controls::select_control(
                            8,
                            &camera_handle.metadata.supported_controls,
                        );
                    }

                    // ── Adjust selected control ──────────────────
                    // Sends AdjustControl(delta) through the channel.
                    // The camera thread processes it between frames and
                    // sends back a ControlAdjusted event.
                    //
                    // The response is handled asynchronously — we don't
                    // wait for it here.  It arrives as a CameraEvent in
                    // a future loop iteration.
                    minifb::Key::Up => {
                        camera_handle.send_adjust_control(
                            CONTROLS[selected_control_index].0,
                            1,
                        );
                    }
                    minifb::Key::Down => {
                        camera_handle.send_adjust_control(
                            CONTROLS[selected_control_index].0,
                            -1,
                        );
                    }

                    // ── Rotate ───────────────────────────────────
                    // Stops recording if aspect ratio changes (90°/270°
                    // swap width and height).
                    minifb::Key::Left => {
                        rotation = pipeline::change_rotation(rotation, -1, &mut recorder);
                    }
                    minifb::Key::Right => {
                        rotation = pipeline::change_rotation(rotation, 1, &mut recorder);
                    }

                    // ── Print settings ───────────────────────────
                    minifb::Key::S => {
                        let _ = controls::print_all_settings(
                            &camera_handle,
                            &camera_handle.metadata.supported_controls,
                        );
                    }

                    _ => {}
                }
            }
        }
        let keyboard_duration = keyboard_start.elapsed();

        // --- receive event from camera thread ---
        //
        // `recv()` blocks until an event arrives.  The event could be:
        // - `Frame(packet)`: a new webcam frame to process and display
        // - `ControlAdjusted(result)`: response to an Up/Down keypress
        // - `ControlInfo(result)`: response to `print_all_settings()`
        // - `Error(msg)`: non-fatal camera error
        //
        // If the channel is disconnected (camera thread exited), we break
        // out of the loop.
        match event_receiver.recv() {
            Ok(CameraEvent::Frame(packet)) => {
                // --- rotate ---
                //
                // `apply_rotation` may or may not allocate depending on the
                // rotation angle.  0° returns the image unchanged.  90°/270°
                // allocate a new RgbImage (width ↔ height).  180° may be
                // in-place depending on the `image` crate implementation.
                //
                // Python analogy: `cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)`
                let rotation_start = Instant::now();
                let mut rotated_frame = pipeline::apply_rotation(packet.image, rotation);
                let rotation_duration = rotation_start.elapsed();

                // --- scale to fit ---
                //
                // Downscales if either dimension exceeds `maximum_dimension`,
                // using a fast integer-ratio nearest-neighbor resize.
                //
                // `arguments.maximum_dimension == 0` means no limit (pass-through).
                // The resize works on the raw byte slice — see `pipeline.rs`
                // for the algorithm details.
                let scale_start = Instant::now();
                if arguments.maximum_dimension > 0 {
                    rotated_frame =
                        pipeline::fast_resize_to_fit(rotated_frame, arguments.maximum_dimension);
                }
                let scale_duration = scale_start.elapsed();

                // --- update display window if dimensions changed ---
                //
                // Rotation (90°/270°) or resize may change the frame dimensions.
                // minifb can't resize its pixel buffer in-place, so we tear
                // down and recreate the window when dimensions change.
                let dimension_update_start = Instant::now();
                let rotated_width = rotated_frame.width();
                let rotated_height = rotated_frame.height();
                if rotated_width != display_width || rotated_height != display_height {
                    display.update_dimensions(
                        rotated_width,
                        rotated_height,
                        window_title,
                    )?;
                    display_width = rotated_width;
                    display_height = rotated_height;
                }
                let dimension_update_duration = dimension_update_start.elapsed();

                // --- feed recorder ---
                //
                // If recording is active, write the processed frame to ffmpeg's
                // stdin.  If the write fails (e.g., ffmpeg crashed), print an
                // error and stop recording.  The recorder is set to `None` so
                // `finish()` won't try to wait on a dead process.
                let record_start = Instant::now();
                if let Some(ref mut active_recorder) = recorder.as_mut() {
                    if let Err(error) =
                        active_recorder.feed_frame(rotated_frame.as_raw())
                    {
                        eprintln!("\nRecording error: {error}");
                        recorder = None;
                        display.set_title(window_title);
                    }
                }
                let record_duration = record_start.elapsed();

                // --- draw overlay bar ---
                //
                // Draws a semi-transparent status bar at the bottom of the
                // frame with FPS, rotation, recording state, and current
                // control info.  The bar is painted directly onto the pixel
                // buffer — no separate window/overlay layer.
                let overlay_state = OverlayState {
                    recording: recorder.is_some(),
                    frame_count: frame_index,
                    frames_per_second,
                    rotation_degrees: rotation as u32 * 90,
                    control_name: CONTROLS[selected_control_index].1.to_string(),
                    control_value: current_control_value,
                };
                draw_overlay(&mut rotated_frame, &overlay_state);

                // --- display (conversion + buffer-update, timed internally) ---
                //
                // `show()` converts the RGB frame to ARGB (for minifb's pixel format)
                // and pushes the buffer to the window.  It returns `false` if the
                // window was closed during the update cycle.
                //
                // The conversion and buffer-update times are measured inside `show()`
                // and retrieved via `last_timing()`.
                if !display.show(&rotated_frame) {
                    camera_handle.send_shutdown();
                    while let Ok(event) = event_receiver.try_recv() {
                        let _ = event;
                    }
                    finish(recorder)?;
                    return Ok(());
                }
                let (conversion_duration, buffer_update_duration) =
                    display.last_timing();

                // --- timing accounting ---
                //
                // All durations are in nanoseconds (`Duration::as_nanos()` returns
                // `u128`).  We accumulate each into its respective counter.
                let total = loop_start.elapsed();

                accumulated_keyboard_nanoseconds += keyboard_duration.as_nanos();
                accumulated_rotation_nanoseconds += rotation_duration.as_nanos();
                accumulated_scale_nanoseconds += scale_duration.as_nanos();
                accumulated_dimension_update_nanoseconds +=
                    dimension_update_duration.as_nanos();
                accumulated_record_nanoseconds += record_duration.as_nanos();
                accumulated_conversion_nanoseconds += conversion_duration;
                accumulated_buffer_update_nanoseconds += buffer_update_duration;
                accumulated_total_nanoseconds += total.as_nanos();
                frame_index += 1;

                // FPS rolling average (30-frame window)
                //
                // Track the duration of each frame iteration, not just the
                // frame-to-frame interval.  When the camera thread is slower
                // than the display, this reflects actual throughput.  When
                // the camera is faster, the channel backpressure (sync_channel(2))
                // naturally paces the loop.
                //
                // Using `VecDeque` with manual capacity management:
                // - `push_back()` adds the latest frame time.
                // - `pop_front()` removes the oldest when capacity is exceeded.
                // - FPS = N frames / sum of their durations (rolling average).
                let frame_seconds = total.as_secs_f64();
                frame_times.push_back(frame_seconds);
                if frame_times.len() > 30 {
                    frame_times.pop_front();
                }
                let frame_seconds_sum: f64 = frame_times.iter().sum();
                if frame_seconds_sum > 0.0 {
                    frames_per_second =
                        frame_times.len() as f64 / frame_seconds_sum;
                }

                // Print per-stage timing averages every TIMING_INTERVAL frames.
                // Pass `&mut` references to the accumulators so timing.rs can
                // reset them to zero after printing.
                timing::print_timing(
                    frame_index,
                    frames_per_second,
                    &mut accumulated_keyboard_nanoseconds,
                    &mut accumulated_rotation_nanoseconds,
                    &mut accumulated_scale_nanoseconds,
                    &mut accumulated_dimension_update_nanoseconds,
                    &mut accumulated_record_nanoseconds,
                    &mut accumulated_conversion_nanoseconds,
                    &mut accumulated_buffer_update_nanoseconds,
                    &mut accumulated_total_nanoseconds,
                );
            }

            // ── Control-adjusted response ────────────────────────────
            //
            // Arrives asynchronously after the camera thread processes an
            // AdjustControl command.  The result is `Ok(new_value)` or
            // `Err(message)`.  We ignore "unsupported" errors quietly since
            // they're common with webcam UVC controls.
            Ok(CameraEvent::ControlAdjusted(result)) => {
                let (_, name) = CONTROLS[selected_control_index];
                match result {
                    Ok(new_value) => {
                        current_control_value = new_value;
                        println!("  {name} = {new_value}");
                    }
                    Err(error) => {
                        if !error.contains("unsupported") {
                            eprintln!("  {error}");
                        }
                    }
                }
            }

            // ── Control-info response ───────────────────────────────
            //
            // Arrives after a GetControlInfo command (triggered by pressing 'S').
            // Prints the control name, current value, and a description of
            // its range/type from the camera firmware.
            Ok(CameraEvent::ControlInfo(result)) => {
                let (_, name) = CONTROLS[selected_control_index];
                match result {
                    Ok((value, description)) => {
                        current_control_value = value;
                        println!("  {name} = {value}  ({description})");
                    }
                    Err(error) => {
                        if !error.contains("unsupported") {
                            eprintln!("  {error}");
                        }
                    }
                }
            }

            // ── Non-fatal camera error ──────────────────────────────
            //
            // Printed to stderr but the loop continues.  Common examples:
            // transient capture failures, control set failures on hardware
            // that doesn't fully implement UVC.
            Ok(CameraEvent::Error(message)) => {
                eprintln!("\nCamera: {message}");
            }

            // ── Channel disconnected ────────────────────────────────
            //
            // `Err(mpsc::RecvError)` means the camera thread has exited
            // (the sender was dropped).  This is the normal shutdown path
            // when the camera thread exits before we send Shutdown — break
            // the loop and clean up.
            Err(_) => {
                break;
            }
        }
    }

    // Post-loop cleanup: finish any active recording and exit.
    finish(recorder)?;
    Ok(())
}

// ── helpers ───────────────────────────────────────────────────────────

/// Finish any active recording and print goodbye.
///
/// `finish()` is called from both the normal loop exit and the early-exit
/// keyboard handler.  Keeping it in one function ensures consistent cleanup.
fn finish(recorder: Option<VideoRecorder>) -> Result<()> {
    if let Some(active_recorder) = recorder {
        active_recorder.finish()?;
    }
    println!("Goodbye.");
    Ok(())
}

/// Toggle recording on/off.
///
/// - **Start**: Creates a `VideoRecorder` which spawns ffmpeg.  Updates the
///   window title to show recording indicator.
/// - **Stop**: Calls `finish()` on the recorder, which closes the stdin pipe
///   and waits for ffmpeg to exit.  Restores the original window title.
///
/// Returns `Some(recorder)` when recording, `None` when stopped.
///
/// ## Rust concept: `Option` state machine
///
/// The pattern `if let Some(x) = current { ...; Ok(None) } else { ...;
/// Ok(Some(new)) }` is a common Rust idiom for toggling state.  The return
/// type `Result<Option<VideoRecorder>>` lets the caller update its local
/// `Option<VideoRecorder>` with the result.
///
/// Python equivalent:
/// ```python
/// def toggle_recording(current, ...):
///     if current is not None:
///         current.finish()
///         return None
///     else:
///         return VideoRecorder.start(...)
///
/// recorder = toggle_recording(recorder, ...)
/// ```
fn toggle_recording(
    current: Option<VideoRecorder>,
    display: &mut DisplayWindow,
    width: u32,
    height: u32,
    frames_per_second: u32,
    output_path: &str,
) -> Result<Option<VideoRecorder>> {
    if let Some(active_recorder) = current {
        println!("\nStopping recording...");
        active_recorder.finish()?;
        display.set_title("Webcam App — [q]uit [r]ecord [←→]rotate");
        Ok(None)
    } else {
        println!("\nRecording started → {output_path}");
        let recorder =
            VideoRecorder::start(width, height, frames_per_second, output_path)?;
        display.set_title("REC  Webcam App — [q]uit [r]stop [←→]rotate");
        Ok(Some(recorder))
    }
}
