//! Camera thread: openpnp-capture DirectShow capture on a dedicated OS thread.
//!
//! Each camera thread creates its own CapContext (COM thread-affine), opens a
//! stream with the requested MJPG format, configures manual exposure, then runs
//! a capture loop synchronized by a BreakableBarrier shared with the gatherer.
//!
//! The thread IS the camera. It owns the COM context and persists for the
//! device's entire lifetime. The `Camera` handle communicates with it via
//! channels. Config changes are applied on the existing thread and COM context.
//!
//! Internal state machine:
//!   Configuring → Streaming → ShuttingDown
//!        ↓            ↓           ↓
//!     Faulted ←────────┴───────────┘
//!
//! The capture loop uses a `FrameStateMachine` from `frame_loop.rs` for
//! frame-level substate tracking and automatic timestamp recording.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::thread;
use std::thread::JoinHandle;

use crate::camera_group::sync_utils::BreakableBarrier;

use super::ffi::*;
use super::frame_loop::{FrameState, FrameStateMachine};
use super::types::{
    CameraConfig, CameraCommand, CameraEvent, CameraIdentity, FrameData, FramePacket,
};

const STABILIZATION_FRAMES: u32 = 30;

/// Spawn a camera capture thread and return the communication channels plus
/// the join handle.
///
/// On success, the camera is streaming — the thread is running the capture
/// loop, synchronized via the shared barrier.
///
/// On failure, the error is returned before any thread is spawned (all
/// failures happen during setup: create context, find format, open stream,
/// configure, stabilize).
pub fn spawn(
    identity: &CameraIdentity,
    shared_config: Arc<std::sync::Mutex<CameraConfig>>,
    barrier: Arc<BreakableBarrier>,
    paused: Arc<AtomicBool>,
    start_frame_number: i64,
) -> anyhow::Result<(
    mpsc::Sender<CameraCommand>,
    mpsc::Receiver<CameraEvent>,
    mpsc::Receiver<FramePacket>,
    JoinHandle<()>,
)> {
    let (command_sender, command_receiver) = mpsc::channel::<CameraCommand>();
    let (event_sender, event_receiver) = mpsc::channel::<CameraEvent>();
    let (frame_sender, frame_receiver) = mpsc::sync_channel::<FramePacket>(1);

    let label = identity.label();
    let identity = identity.clone();

    let thread_handle = thread::Builder::new()
        .name(label.clone())
        .spawn(move || {
        let result = run_camera_thread(
            shared_config,
            &identity,
            &label,
            &command_receiver,
            &event_sender,
            &frame_sender,
            &barrier,
            &paused,
            start_frame_number,
        );
        if let Err(error) = result {
            let _ = event_sender.send(CameraEvent::Error(format!(
                "Camera {label} thread error: {error}"
            )));
        }
    })?;

    Ok((command_sender, event_receiver, frame_receiver, thread_handle))
}

enum CommandResult {
    None,
    Shutdown,
    Configure(CameraConfig),
}

/// Check the command channel. Returns the first pending command, or None if empty.
fn check_commands(command_receiver: &mpsc::Receiver<CameraCommand>) -> CommandResult {
    match command_receiver.try_recv() {
        Ok(CameraCommand::Shutdown) => CommandResult::Shutdown,
        Ok(CameraCommand::Configure { config }) => CommandResult::Configure(config),
        Err(mpsc::TryRecvError::Empty) => CommandResult::None,
        Err(mpsc::TryRecvError::Disconnected) => CommandResult::Shutdown,
    }
}

/// Apply a new config to the running camera.
///
/// For exposure-only changes: just reconfigures exposure in-place.
/// For resolution/framerate changes: closes the current stream, finds
/// the best matching MJPG format, opens a new stream, and re-applies
/// exposure on the new stream. The camera thread stays alive — only
/// the internal CaptureStream is replaced.
///
/// Returns the (possibly new) stream, actual_width, and actual_height.
unsafe fn apply_config(
    ctx: CapContext,
    stream: CapStream,
    label: &str,
    new_config: &CameraConfig,
    old_config: &CameraConfig,
    actual_width: u32,
    actual_height: u32,
    shared_config: &Arc<std::sync::Mutex<CameraConfig>>,
) -> (CapStream, u32, u32) { unsafe {
    let needs_restart = actual_width != new_config.width
        || actual_height != new_config.height
        || (old_config.framerate - new_config.framerate).abs() > 0.1;

    if needs_restart {
         Cap_closeStream(ctx, stream) ;

        let format_info = match find_best_mjpg(
            ctx,
            new_config.camera_index,
            new_config.width,
            new_config.height,
            new_config.framerate,
            label,
        ) {
            Ok(f) => f,
            Err(e) => {
                tracing::error!("Camera {label}: failed to find format for new config: {e}");
                // Reopen with the original format as fallback
                match find_best_mjpg(ctx, old_config.camera_index, old_config.width, old_config.height, old_config.framerate, label) {
                    Ok(f) => f,
                    Err(_) => {
                        tracing::error!("Camera {label}: fatal — cannot reopen stream");
                        return (stream, actual_width, actual_height);
                    }
                }
            }
        };

        let new_stream = match open_stream_raw(ctx, new_config.camera_index, label, &format_info) {
            Ok(s) => s,
            Err(e) => {
                tracing::error!("Camera {label}: failed to open new stream: {e}");
                return (stream, actual_width, actual_height);
            }
        };

        configure_exposure(ctx, new_stream, label, &new_config.exposure_mode, new_config.exposure);

        // Write actual negotiated settings back to shared config
        if let Ok(mut guard) = shared_config.lock() {
            guard.framerate = format_info.fps as f64;
            guard.width = format_info.width;
            guard.height = format_info.height;
        }

        tracing::debug!(
            "Camera {label}: stream restarted — {actual_width}x{actual_height} @{:.0}fps → {}x{} @{}fps",
            old_config.framerate,
            format_info.width, format_info.height, format_info.fps,
        );
        (new_stream, format_info.width, format_info.height)
    } else {
        configure_exposure(ctx, stream, label, &new_config.exposure_mode, new_config.exposure);
        tracing::debug!("Camera {label}: applied config (exposure={})", new_config.exposure);
        (stream, actual_width, actual_height)
    }
}}

fn run_camera_thread(
    shared_config: Arc<std::sync::Mutex<CameraConfig>>,
    identity: &CameraIdentity,
    label: &str,
    command_receiver: &mpsc::Receiver<CameraCommand>,
    event_sender: &mpsc::Sender<CameraEvent>,
    frame_sender: &mpsc::SyncSender<FramePacket>,
    barrier: &BreakableBarrier,
    paused: &Arc<AtomicBool>,
    start_frame_number: i64,
) -> anyhow::Result<()> {
    unsafe {
        let ctx = Cap_createContext();
        if ctx.is_null() {
            anyhow::bail!("Cap_createContext returned null");
        }

        let initial_config = {
            shared_config.lock().unwrap().clone()
        };

        let format_info = find_best_mjpg(
            ctx,
            initial_config.camera_index,
            initial_config.width,
            initial_config.height,
            initial_config.framerate,
            label,
        )?;

        // Write actual negotiated settings back to shared config so that
        // external consumers (recording path, API responses) see the real values.
        {
            let mut guard = shared_config.lock().unwrap();
            guard.framerate = format_info.fps as f64;
            guard.width = format_info.width;
            guard.height = format_info.height;
        }

        let mut stream =
            open_stream_raw(ctx, initial_config.camera_index, label, &format_info)?;

        configure_exposure(ctx, stream, label, &initial_config.exposure_mode, initial_config.exposure);
        stabilize_raw(ctx, stream, label);

        let mut actual_width = format_info.width;
        let mut actual_height = format_info.height;

        tracing::info!(
            "Camera {label}: capture loop raw-MJPEG ({actual_width}x{actual_height} @{}fps)",
            format_info.fps,
        );

        let _ = event_sender.send(CameraEvent::Ready);
        let mut frame_sm = FrameStateMachine::new(start_frame_number);
        let mut raw_buffer: Vec<u8> = Vec::new();
        let mut active_config = initial_config;

        loop {
            // ── Process pending commands ──
            match check_commands(command_receiver) {
                CommandResult::Shutdown => {
                    tracing::info!("Camera {label}: shutdown");
                    break;
                }
                CommandResult::Configure(new_config) => {
                    (stream, actual_width, actual_height) = apply_config(
                        ctx, stream, label, &new_config, &active_config,
                        actual_width, actual_height, &shared_config,
                    );
                    active_config = new_config;
                    // Pull actual negotiated framerate/width/height from the
                    // shared config (written by apply_config for restarts, or
                    // by Camera::configure for exposure-only changes).
                    if let Ok(guard) = shared_config.lock() {
                        active_config.framerate = guard.framerate;
                        active_config.width = guard.width;
                        active_config.height = guard.height;
                    }
                }
                CommandResult::None => {}
            }

            // ── Paused spin ────────────────────────────────────────────
            // Placed AFTER the previous cycle's barrier/increment so the
            // camera has completed its last frame before spinning. Still
            // checks commands so Configure/Shutdown remain responsive.
            while paused.load(Ordering::SeqCst) {
                match check_commands(command_receiver) {
                    CommandResult::Shutdown => {
                        tracing::info!("Camera {label}: shutdown while paused");
                        Cap_closeStream(ctx, stream);
                        Cap_releaseContext(ctx);
                        return Ok(());
                    }
                    CommandResult::Configure(new_config) => {
                        (stream, actual_width, actual_height) = apply_config(
                            ctx, stream, label, &new_config, &active_config,
                            actual_width, actual_height, &shared_config,
                        );
                        active_config = new_config;
                    // Pull actual negotiated framerate/width/height from the
                    // shared config (written by apply_config for restarts, or
                    // by Camera::configure for exposure-only changes).
                    if let Ok(guard) = shared_config.lock() {
                        active_config.framerate = guard.framerate;
                        active_config.width = guard.width;
                        active_config.height = guard.height;
                    }
                    }
                    CommandResult::None => {
                        std::thread::sleep(std::time::Duration::from_millis(1));
                    }
                }
            }
            // ── End paused spin ────────────────────────────────────────

            // ── Spin on hasNewFrame ──
            let wait_start = std::time::Instant::now();
            loop {
                match check_commands(command_receiver) {
                    CommandResult::Shutdown => {
                        tracing::info!("Camera {label}: shutdown during hasNewFrame");
                        Cap_closeStream(ctx, stream);
                        Cap_releaseContext(ctx);
                        return Ok(());
                    }
                    CommandResult::Configure(new_config) => {
                        (stream, actual_width, actual_height) = apply_config(
                            ctx, stream, label, &new_config, &active_config,
                            actual_width, actual_height, &shared_config,
                        );
                        active_config = new_config;
                    // Pull actual negotiated framerate/width/height from the
                    // shared config (written by apply_config for restarts, or
                    // by Camera::configure for exposure-only changes).
                    if let Ok(guard) = shared_config.lock() {
                        active_config.framerate = guard.framerate;
                        active_config.width = guard.width;
                        active_config.height = guard.height;
                    }
                    }
                    CommandResult::None => {}
                }
                if Cap_hasNewFrame(ctx, stream) != 0 {
                    break;
                }
                std::thread::yield_now();
                if wait_start.elapsed().as_secs() > 5 {
                    let msg = format!(
                        "Camera {label}: timeout waiting for frame {}",
                        frame_sm.frame_number()
                    );
                    let _ = event_sender.send(CameraEvent::Error(msg));
                    Cap_closeStream(ctx, stream);
                    Cap_releaseContext(ctx);
                    return Ok(());
                }
            }

            // Stamp `frame_available_ns` at the precise moment Cap_hasNewFrame
            // returned true — the hardware-ready instant, before any capture work.
            let frame_available_ns =
                crate::timestamps::performance::performance_counter_nanoseconds();
            // ── Capture the frame and copy bytes into a heap-owned Vec ──
            // Cap_getFrameSize and Cap_captureFrameRaw are not atomic — the
            // DirectShow callback thread can deliver a differently-sized
            // MJPEG frame between the two calls. Retry on buffer-too-small.
            let mut out_bytes: u32 = 0;
            let mut capture_ok = false;
            for _retry in 0..3 {
                let mut frame_size: u32 = 0;
                if Cap_getFrameSize(ctx, stream, &mut frame_size) != CAPRESULT_OK
                    || frame_size == 0
                {
                    let msg = format!(
                        "Camera {label}: getFrameSize failed or returned 0 at frame {}",
                        frame_sm.frame_number()
                    );
                    let _ = event_sender.send(CameraEvent::Error(msg));
                    break;
                }
                let needed = frame_size as usize;
                if raw_buffer.len() < needed {
                    raw_buffer.resize(needed * 2, 0);
                }
                let result = Cap_captureFrameRaw(
                    ctx, stream,
                    raw_buffer.as_mut_ptr(), raw_buffer.len() as u32,
                    &mut out_bytes,
                );
                if result == CAPRESULT_OK {
                    capture_ok = true;
                    break;
                }
                // Buffer too small — out_bytes carries the actual size,
                // grow and retry.
                if out_bytes as usize > raw_buffer.len() {
                    raw_buffer.resize(out_bytes as usize * 2, 0);
                    continue;
                }
                let msg = format!(
                    "Camera {label}: captureFrameRaw failed at frame {} ({})",
                    frame_sm.frame_number(),
                    result_name(result)
                );
                let _ = event_sender.send(CameraEvent::Error(msg));
                break;
            }
            if !capture_ok {
                break;
            }
            let frame_data = FrameData::Mjpg(raw_buffer[..out_bytes as usize].to_vec());
            // Stamp `post_jpeg_extract_ns` immediately after the raw bytes are
            // owned by a heap Vec. The interval (post_jpeg_extract - frame_available)
            // covers Cap_captureFrameRaw + the to_vec() copy — i.e. the full
            // device-buffer → heap-owned JPEG path. This is the OpenCV
            // `cap.read()` comparison metric.
            let post_jpeg_extract_ns =
                crate::timestamps::performance::performance_counter_nanoseconds();
            if let Err(e) = frame_sm.begin_capture(frame_available_ns) {
                tracing::error!("Camera {label}: invalid frame state transition: {e}");
            }
            frame_sm.timestamps.post_jpeg_extract_ns = post_jpeg_extract_ns;

            if let Err(e) = frame_sm.transition_to(FrameState::Sending) {
                tracing::error!("Camera {label}: invalid frame state transition: {e}");
            }

            // Stamp `pre_send_ns` immediately before the channel send, so the
            // packet's cloned timestamps include the correct value.
            frame_sm.timestamps.pre_send_ns =
                crate::timestamps::performance::performance_counter_nanoseconds();

            let packet = FramePacket {
                data: frame_data,
                width: actual_width,
                height: actual_height,
                rotation: active_config.rotation,
                timestamps: frame_sm.timestamps.clone(),
                identity: identity.clone(),
                frame_number: frame_sm.frame_number(),
            };

            if frame_sender.send(packet).is_err() {
                break;
            }

            if let Err(e) = frame_sm.transition_to(FrameState::AtBarrier) {
                tracing::error!("Camera {label}: invalid frame state transition: {e}");
            }

            // The camera calls barrier.wait() AFTER the packet has been sent
            // downstream. That ordering means any timestamps bracketing this
            // barrier call cannot be put on this iteration's packet — they
            // would belong to the previous-or-next iteration and create
            // off-by-one attribution bugs in the gatherer's stats. We do not
            // stamp pre_barrier/post_barrier into the packet for that reason
            // (see note in camera/types.rs). `loop_start_ns` IS still stamped
            // because it marks the BEGINNING of the next iteration's frame
            // packet, which the gatherer can attribute correctly.
            if !barrier.wait() {
                tracing::info!("Camera {label}: barrier broken (shutdown)");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }
            let post_barrier_ns =
                crate::timestamps::performance::performance_counter_nanoseconds();
            // `post_barrier_ns` IS the next iteration's `loop_start_ns` by
            // definition (the camera exits the barrier and immediately begins
            // the next capture cycle).
            frame_sm.timestamps.loop_start_ns = post_barrier_ns;
            if let Err(e) = frame_sm.transition_to(FrameState::WaitingForFrame) {
                tracing::error!("Camera {label}: invalid frame state transition: {e}");
            }
            frame_sm.increment_frame();
        }

        Cap_closeStream(ctx, stream);
        Cap_releaseContext(ctx);
        tracing::info!("Camera {label}: shutdown complete");
    }
    Ok(())
}

/// Find the best MJPG format matching the requested dimensions and framerate.
unsafe fn find_best_mjpg(
    ctx: CapContext,
    index: u32,
    requested_width: u32,
    requested_height: u32,
    requested_framerate: f64,
    label: &str,
) -> anyhow::Result<CapFormatInfo> {
    let device_count = unsafe { Cap_getDeviceCount(ctx) };
    if index >= device_count {
        anyhow::bail!("Camera index {index} not found (only {device_count} devices)");
    }

    let num_formats = unsafe { Cap_getNumFormats(ctx, index) };
    if num_formats <= 0 {
        anyhow::bail!("Camera {label}: no formats available");
    }

    let want_fps = requested_framerate > 0.0;

    if want_fps {
        // Pass 1: exact resolution + framerate match
        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK {
                if info.fourcc == FOURCC_MJPG
                    && info.width == requested_width
                    && info.height == requested_height
                    && info.fps as f64 == requested_framerate
                {
                    tracing::trace!(
                        "Camera {label}: format {f} ({}x{} @{}fps MJPG) — exact match",
                        info.width, info.height, info.fps,
                    );
                    return Ok(info);
                }
            }
        }

        // Pass 2: exact resolution, any MJPG (pick closest framerate)
        let mut best: Option<(CapFormatID, CapFormatInfo)> = None;
        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK
                && info.fourcc == FOURCC_MJPG
                && info.width == requested_width
                && info.height == requested_height
            {
                match best {
                    None => best = Some((f as CapFormatID, info)),
                    Some((_, ref best_info)) => {
                        let best_fps_diff = (best_info.fps as f64 - requested_framerate).abs();
                        let this_fps_diff = (info.fps as f64 - requested_framerate).abs();
                        if this_fps_diff < best_fps_diff {
                            best = Some((f as CapFormatID, info));
                        }
                    }
                }
            }
        }
        if let Some((_fid, info)) = best {
            tracing::trace!(
                "Camera {label}: format ({}x{} @{}fps MJPG) — resolution match",
                info.width, info.height, info.fps,
            );
            return Ok(info);
        }

        // Pass 3: any MJPG format (closest framerate fallback)
        let mut best: Option<(CapFormatID, CapFormatInfo)> = None;
        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK
                && info.fourcc == FOURCC_MJPG
            {
                match best {
                    None => best = Some((f as CapFormatID, info)),
                    Some((_, ref best_info)) => {
                        let best_fps_diff = (best_info.fps as f64 - requested_framerate).abs();
                        let this_fps_diff = (info.fps as f64 - requested_framerate).abs();
                        if this_fps_diff < best_fps_diff {
                            best = Some((f as CapFormatID, info));
                        }
                    }
                }
            }
        }
        if let Some((_fid, info)) = best {
            tracing::trace!(
                "Camera {label}: format {_fid} ({}x{} @{}fps MJPG) — best available",
                info.width, info.height, info.fps,
            );
            return Ok(info);
        }
    } else {
        // No specific framerate requested — prioritize resolution match.
        // Pass 1: exact MJPG resolution match (any framerate).
        let mut best: Option<(CapFormatID, CapFormatInfo)> = None;
        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK
                && info.fourcc == FOURCC_MJPG
                && info.width == requested_width
                && info.height == requested_height
            {
                match best {
                    None => best = Some((f as CapFormatID, info)),
                    Some((_, ref best_info)) => {
                        if info.fps > best_info.fps {
                            best = Some((f as CapFormatID, info));
                        }
                    }
                }
            }
        }
        if let Some((_fid, info)) = best {
            tracing::trace!(
                "Camera {label}: format ({}x{} @{}fps MJPG) — resolution match (no framerate target)",
                info.width, info.height, info.fps,
            );
            return Ok(info);
        }

        // Pass 2: if resolution not found in MJPG, fall back to any MJPG,
        // picking highest FPS with tie-break on pixel area.
        let mut best: Option<(CapFormatID, CapFormatInfo)> = None;
        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK
                && info.fourcc == FOURCC_MJPG
            {
                match best {
                    None => best = Some((f as CapFormatID, info)),
                    Some((_, ref best_info)) => {
                        if info.fps > best_info.fps
                            || (info.fps == best_info.fps
                                && info.width * info.height
                                    > best_info.width * best_info.height)
                        {
                            best = Some((f as CapFormatID, info));
                        }
                    }
                }
            }
        }
        if let Some((_fid, info)) = best {
            tracing::trace!(
                "Camera {label}: format ({}x{} @{}fps MJPG) — resolution not matched, highest-FPS fallback",
                info.width, info.height, info.fps,
            );
            return Ok(info);
        }
    }

    anyhow::bail!("Camera {label}: no MJPG format found")
}

unsafe fn open_stream_raw(
    ctx: CapContext,
    index: u32,
    label: &str,
    info: &CapFormatInfo,
) -> anyhow::Result<CapStream> {
    let num_formats = unsafe { Cap_getNumFormats(ctx, index) };
    let mut format_id: Option<CapFormatID> = None;
    for f in 0..num_formats {
        let mut check = CapFormatInfo::default();
        if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut check) } == CAPRESULT_OK
            && check.fourcc == info.fourcc
            && check.width == info.width
            && check.height == info.height
            && check.fps == info.fps
        {
            format_id = Some(f as CapFormatID);
            break;
        }
    }
    let format_id = format_id.ok_or_else(|| {
        anyhow::anyhow!("Camera {label}: could not re-find matching format_id for raw stream")
    })?;

    let stream = unsafe { Cap_openStreamRaw(ctx, index, format_id) };
    if stream < 0 {
        anyhow::bail!(
            "Camera {label}: Cap_openStreamRaw returned {stream} (camera may not support raw MJPEG)"
        );
    }
    tracing::info!(
        "Camera {label}: raw MJPEG stream opened (format={format_id} stream={stream} {}x{})",
        info.width, info.height,
    );
    Ok(stream)
}

unsafe fn configure_exposure(
    ctx: CapContext,
    stream: CapStream,
    label: &str,
    exposure_mode: &str,
    target_exposure: i32,
) {
    // USB UVC cameras report min=-13 max=-1, but only -11..-5 produce
    // meaningful exposure changes. Values outside this range are either
    // clamped by the hardware (full black at ≤-11, full bright at ≥-5)
    // or produce unreliable results.
    let clamped = target_exposure.clamp(-11, -5);
    if clamped != target_exposure {
        tracing::debug!(
            "Camera {label}: exposure {target_exposure} clamped to {clamped} (valid range -11..-5)"
        );
    }

    let mut min: i32 = 0;
    let mut max: i32 = 0;
    let mut default: i32 = 0;
    let _ = unsafe {
        Cap_getPropertyLimits(ctx, stream, CAPPROPID_EXPOSURE, &mut min, &mut max, &mut default)
    };
    if exposure_mode == "AUTO" {
        unsafe { Cap_setAutoProperty(ctx, stream, CAPPROPID_EXPOSURE, 1) };
        tracing::debug!("Camera {label}: exposure set to AUTO (limits min={min} max={max} default={default})");
    } else {
        unsafe { Cap_setAutoProperty(ctx, stream, CAPPROPID_EXPOSURE, 0) };
        unsafe { Cap_setProperty(ctx, stream, CAPPROPID_EXPOSURE, clamped) };
        tracing::debug!("Camera {label}: exposure set to {clamped} (limits min={min} max={max} default={default})");
    }
}

fn stabilize_raw(ctx: CapContext, stream: CapStream, label: &str) {
    let mut buffer: Vec<u8> = Vec::new();
    for i in 0..STABILIZATION_FRAMES {
        loop {
            if check_shutdown_for_stabilize() {
                return;
            }
            if unsafe { Cap_hasNewFrame(ctx, stream) } != 0 {
                break;
            }
            std::thread::yield_now();
        }
        let mut frame_size: u32 = 0;
        if unsafe { Cap_getFrameSize(ctx, stream, &mut frame_size) } != CAPRESULT_OK
            || frame_size == 0
        {
            tracing::warn!(
                "Camera {label}: raw stabilize frame {i} getFrameSize failed or size=0, skipping"
            );
            continue;
        }
        if buffer.len() < frame_size as usize {
            buffer.resize(frame_size as usize, 0);
        }
        let mut out_bytes: u32 = 0;
        unsafe {
            Cap_captureFrameRaw(ctx, stream, buffer.as_mut_ptr(), frame_size, &mut out_bytes);
        }
        let first_bytes = &buffer[..(out_bytes as usize).min(16)];
        tracing::trace!(
            "Camera {label}: raw stabilize frame {i}: {out_bytes}B  first_16={first_bytes:02X?}"
        );
    }
    tracing::debug!("Camera {label}: raw stabilization complete ({STABILIZATION_FRAMES} frames)");
}

fn check_shutdown_for_stabilize() -> bool {
    false
}
