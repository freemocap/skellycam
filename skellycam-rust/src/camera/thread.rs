//! Camera thread: openpnp-capture DirectShow capture on a dedicated OS thread.
//!
//! Each camera thread creates its own CapContext (COM thread-affine), opens a
//! stream with the requested MJPG format, configures manual exposure, then runs
//! a capture loop synchronized by a BreakableBarrier shared with the gatherer.
//!
//! Two capture modes:
//!   - Raw MJPEG (default): `Cap_openStreamRaw` + `Cap_captureFrameRaw`
//!     produces `FrameData::Mjpg` — JPEG bytes pass through without decode.
//!   - RGB (fallback): `Cap_openStream` + `Cap_captureFrame` produces
//!     `FrameData::Rgb` — openpnp-capture decodes MJPEG→RGB internally.

use std::sync::mpsc;
use std::sync::Arc;
use std::thread;

use crate::sync_utils::BreakableBarrier;

use super::ffi::*;
use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket, FrameLifecycleTimestamps};
use crate::timestamps::performance::performance_counter_nanoseconds;

const TARGET_EXPOSURE: i32 = -7;
const STABILIZATION_FRAMES: u32 = 30;

pub fn spawn_camera_thread(
    index: u32,
    requested_width: u32,
    requested_height: u32,
    identity: CameraIdentity,
    barrier: Arc<BreakableBarrier>,
    use_raw: bool,
) -> (
    CameraHandle,
    mpsc::Receiver<CameraEvent>,
    mpsc::Receiver<FramePacket>,
) {
    let (command_sender, command_receiver) = mpsc::channel::<CameraCommand>();
    let (event_sender, event_receiver) = mpsc::channel::<CameraEvent>();
    let (frame_sender, frame_receiver) = mpsc::sync_channel::<FramePacket>(1);

    let handle = CameraHandle {
        command_sender: command_sender.clone(),
        identity: identity.clone(),
        width: requested_width,
        height: requested_height,
    };

    let label = identity.label();

    thread::spawn(move || {
        let result = run_camera_thread(
            index,
            requested_width,
            requested_height,
            use_raw,
            &identity,
            &label,
            &command_receiver,
            &event_sender,
            &frame_sender,
            &barrier,
        );
        if let Err(error) = result {
            let _ = event_sender.send(CameraEvent::Error(format!(
                "Camera {label} thread error: {error}"
            )));
        }
    });

    (handle, event_receiver, frame_receiver)
}

/// Check for shutdown on the command channel. Returns true if shutdown received.
fn check_shutdown(command_receiver: &mpsc::Receiver<CameraCommand>) -> bool {
    match command_receiver.try_recv() {
        Ok(CameraCommand::Shutdown) => true,
        Err(mpsc::TryRecvError::Empty) => false,
        Err(mpsc::TryRecvError::Disconnected) => true,
    }
}

fn run_camera_thread(
    index: u32,
    requested_width: u32,
    requested_height: u32,
    use_raw: bool,
    identity: &CameraIdentity,
    label: &str,
    command_receiver: &mpsc::Receiver<CameraCommand>,
    event_sender: &mpsc::Sender<CameraEvent>,
    frame_sender: &mpsc::SyncSender<FramePacket>,
    barrier: &BreakableBarrier,
) -> anyhow::Result<()> {
    unsafe {
        let ctx = Cap_createContext();
        if ctx.is_null() {
            anyhow::bail!("Cap_createContext returned null");
        }

        // Enumerate formats to get width/height metadata (needed for handle,
        // even in raw mode where the stream is opened without a format_id).
        let format_info = find_best_mjpg(ctx, index, requested_width, requested_height, label)?;

        let stream = if use_raw {
            open_stream_raw(ctx, index, label, &format_info)?
        } else {
            open_stream_rgb(ctx, index, label, &format_info)?
        };

        configure_exposure(ctx, stream, label);

        if use_raw {
            stabilize_raw(ctx, stream, label);
        } else {
            stabilize_rgb(ctx, stream, format_info.width, format_info.height);
        }

        let actual_width = format_info.width;
        let actual_height = format_info.height;

        tracing::info!(
            "Camera {label}: capture loop {} ({actual_width}x{actual_height})",
            if use_raw { "raw-MJPEG" } else { "RGB-decoded" },
        );

        let mut frame_number: i64 = 0;

        // Buffer reused across frames — sized dynamically for raw, fixed for RGB.
        let rgb_buffer_size = (actual_width * actual_height * 3) as usize;
        let mut rgb_buffer: Vec<u8> = if !use_raw { vec![0u8; rgb_buffer_size] } else { Vec::new() };
        let mut raw_buffer: Vec<u8> = Vec::new();

        loop {
            // ── loop_start_ns ──
            let loop_start_ns = performance_counter_nanoseconds();

            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown");
                break;
            }

            // Wait for next hardware frame
            let wait_start = std::time::Instant::now();
            loop {
                if check_shutdown(command_receiver) {
                    tracing::info!("Camera {label}: shutdown during hasNewFrame");
                    Cap_closeStream(ctx, stream);
                    Cap_releaseContext(ctx);
                    return Ok(());
                }
                if Cap_hasNewFrame(ctx, stream) != 0 {
                    break;
                }
                std::thread::yield_now();
                if wait_start.elapsed().as_secs() > 5 {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Camera {label}: timeout waiting for frame {frame_number}"
                    )));
                    Cap_closeStream(ctx, stream);
                    Cap_releaseContext(ctx);
                    return Ok(());
                }
            }

            let frame_available_ns = performance_counter_nanoseconds();

            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown before barrier");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            let pre_barrier_ns = performance_counter_nanoseconds();

            if !barrier.wait() {
                tracing::info!("Camera {label}: barrier broken (shutdown)");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            let post_barrier_ns = performance_counter_nanoseconds();

            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown after barrier");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            let pre_capture_ns = performance_counter_nanoseconds();

            let frame_data = if use_raw {
                // Raw MJPEG: get frame size, ensure buffer, capture
                let mut frame_size: u32 = 0;
                if Cap_getFrameSize(ctx, stream, &mut frame_size) != CAPRESULT_OK || frame_size == 0 {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Camera {label}: getFrameSize failed or returned 0 at frame {frame_number}"
                    )));
                    break;
                }
                if raw_buffer.len() < frame_size as usize {
                    raw_buffer.resize(frame_size as usize, 0);
                }
                let mut out_bytes: u32 = 0;
                let result = Cap_captureFrameRaw(
                    ctx, stream,
                    raw_buffer.as_mut_ptr(), frame_size,
                    &mut out_bytes,
                );
                if result != CAPRESULT_OK {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Camera {label}: captureFrameRaw failed at frame {frame_number} ({})",
                        result_name(result)
                    )));
                    break;
                }
                FrameData::Mjpg(raw_buffer[..out_bytes as usize].to_vec())
            } else {
                let result = Cap_captureFrame(ctx, stream, rgb_buffer.as_mut_ptr(), rgb_buffer_size as u32);
                if result != CAPRESULT_OK {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Camera {label}: captureFrame failed at frame {frame_number} ({})",
                        result_name(result)
                    )));
                    break;
                }
                FrameData::Rgb(rgb_buffer.clone())
            };

            let post_capture_ns = performance_counter_nanoseconds();

            // Log capture details + hex-dump first bytes
            {
                let data_kb = frame_data.len() as f64 / 1024.0;
                let first_bytes = &frame_data.as_bytes()[..frame_data.len().min(16)];
                let is_jpeg = frame_data.as_bytes().len() >= 2
                    && frame_data.as_bytes()[0] == 0xFF
                    && frame_data.as_bytes()[1] == 0xD8;
                let jpeg_flag = if is_jpeg { "VALID-JPEG" } else { "NO-JPEG-MAGIC" };
                if frame_number % 30 == 0 || !is_jpeg {
                    let capture_us = (post_capture_ns - pre_capture_ns) as f64 / 1000.0;
                    let wait_ms = (frame_available_ns - loop_start_ns) as f64 / 1_000_000.0;
                    tracing::warn!(
                        "Camera {label}: frame {frame_number} | {data_kb:.0}KB | {jpeg_flag} | wait={wait_ms:.1}ms capture={capture_us:.0}µs | first_16={first_bytes:02X?}",
                    );
                }
            }

            let mut packet = FramePacket {
                data: frame_data,
                width: actual_width,
                height: actual_height,
                timestamps: FrameLifecycleTimestamps {
                    loop_start_ns,
                    frame_available_ns,
                    pre_barrier_ns,
                    post_barrier_ns,
                    pre_capture_ns,
                    post_capture_ns,
                    pre_send_ns: 0,
                    post_send_ns: 0,
                    gatherer_received_ns: 0,
                },
                identity: identity.clone(),
                frame_number,
            };

            packet.timestamps.pre_send_ns = performance_counter_nanoseconds();
            frame_number += 1;

            if frame_sender.send(packet).is_err() {
                break;
            }
        }

        Cap_closeStream(ctx, stream);
        Cap_releaseContext(ctx);
        tracing::info!("Camera {label}: shutdown complete");
    }
    Ok(())
}

/// Find the best MJPG format matching the requested dimensions.
/// Returns format info; does NOT open the stream.
unsafe fn find_best_mjpg(
    ctx: CapContext,
    index: u32,
    requested_width: u32,
    requested_height: u32,
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

    // First pass: exact match
    for f in 0..num_formats {
        let mut info = CapFormatInfo::default();
        if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK {
            if info.fourcc == FOURCC_MJPG
                && info.width == requested_width
                && info.height == requested_height
            {
                tracing::info!(
                    "Camera {label}: format {f} ({}x{} @{}fps MJPG) — exact match",
                    info.width, info.height, info.fps,
                );
                return Ok(info);
            }
        }
    }

    // Second pass: any MJPG
    for f in 0..num_formats {
        let mut info = CapFormatInfo::default();
        if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK
            && info.fourcc == FOURCC_MJPG
        {
            tracing::info!(
                "Camera {label}: format {f} ({}x{} @{}fps MJPG) — best available",
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
    // Re-find the matching format_id (same approach as open_stream_rgb)
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
    let format_id = format_id
        .ok_or_else(|| anyhow::anyhow!("Camera {label}: could not re-find matching format_id for raw stream"))?;

    let stream = unsafe { Cap_openStreamRaw(ctx, index, format_id) };
    if stream < 0 {
        anyhow::bail!("Camera {label}: Cap_openStreamRaw returned {stream} (camera may not support raw MJPEG)");
    }
    tracing::info!(
        "Camera {label}: raw MJPEG stream opened (format={format_id} stream={stream} {}x{})",
        info.width, info.height,
    );
    Ok(stream)
}

unsafe fn open_stream_rgb(
    ctx: CapContext,
    index: u32,
    label: &str,
    info: &CapFormatInfo,
) -> anyhow::Result<CapStream> {
    // We need the format_id that corresponds to the chosen info.
    // Re-enumerate to find it (cheap — just integer lookups).
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
    let format_id = format_id
        .ok_or_else(|| anyhow::anyhow!("Camera {label}: could not re-find matching format_id"))?;

    let stream = unsafe { Cap_openStream(ctx, index, format_id) };
    if stream < 0 {
        anyhow::bail!("Camera {label}: Cap_openStream returned {stream}");
    }
    tracing::info!("Camera {label}: RGB stream opened (format={format_id} stream={stream})");
    Ok(stream)
}

unsafe fn configure_exposure(ctx: CapContext, stream: CapStream, label: &str) {
    let mut min: i32 = 0;
    let mut max: i32 = 0;
    let mut default: i32 = 0;
    let _ = unsafe {
        Cap_getPropertyLimits(ctx, stream, CAPPROPID_EXPOSURE, &mut min, &mut max, &mut default)
    };
    tracing::info!("Camera {label}: exposure limits min={min} max={max} default={default}");

    unsafe { Cap_setAutoProperty(ctx, stream, CAPPROPID_EXPOSURE, 0) };
    unsafe { Cap_setProperty(ctx, stream, CAPPROPID_EXPOSURE, TARGET_EXPOSURE) };
    tracing::info!("Camera {label}: exposure set to {TARGET_EXPOSURE}");
}

unsafe fn stabilize_rgb(ctx: CapContext, stream: CapStream, width: u32, height: u32) {
    let frame_bytes = (width * height * 3) as usize;
    let mut buffer: Vec<u8> = vec![0u8; frame_bytes];
    for _ in 0..STABILIZATION_FRAMES {
        loop {
            if unsafe { Cap_hasNewFrame(ctx, stream) } != 0 {
                break;
            }
            std::thread::yield_now();
        }
        unsafe { Cap_captureFrame(ctx, stream, buffer.as_mut_ptr(), frame_bytes as u32) };
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
        if unsafe { Cap_getFrameSize(ctx, stream, &mut frame_size) } != CAPRESULT_OK || frame_size == 0 {
            tracing::warn!("Camera {label}: raw stabilize frame {i} getFrameSize failed or size=0, skipping");
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
        tracing::debug!(
            "Camera {label}: raw stabilize frame {i}: {out_bytes}B  first_16={first_bytes:02X?}"
        );
    }
    tracing::info!("Camera {label}: raw stabilization complete ({STABILIZATION_FRAMES} frames)");
}

/// No-op in raw mode — shutdown handling is done in the main loop.
/// This exists so we can add per-frame checks during stabilization if needed.
fn check_shutdown_for_stabilize() -> bool {
    false
}
