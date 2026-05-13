//! Camera thread: openpnp-capture DirectShow capture on a dedicated OS thread.
//!
//! Each camera thread creates its own CapContext (COM thread-affine), opens a
//! stream with the requested MJPG format, configures manual exposure, then runs
//! a capture loop synchronized by a BreakableBarrier shared with the gatherer.

use std::sync::mpsc;
use std::sync::Arc;
use std::thread;

use crate::sync_utils::BreakableBarrier;

use super::ffi::*;
use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket};
use crate::timestamps::performance::performance_counter_nanoseconds;

const TARGET_EXPOSURE: i32 = -7;
const STABILIZATION_FRAMES: u32 = 30;

pub fn spawn_camera_thread(
    index: u32,
    requested_width: u32,
    requested_height: u32,
    identity: CameraIdentity,
    barrier: Arc<BreakableBarrier>,
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

        let open_result = open_camera_stream(ctx, index, requested_width, requested_height, label);
        let (stream, actual_width, actual_height) = match open_result {
            Ok(v) => v,
            Err(error) => {
                Cap_releaseContext(ctx);
                return Err(error);
            }
        };

        configure_exposure(ctx, stream, label);
        stabilize(ctx, stream, actual_width, actual_height);

        tracing::info!("Camera {label}: capture loop ({actual_width}x{actual_height})");

        let frame_bytes = (actual_width * actual_height * 3) as usize;
        let mut buffer: Vec<u8> = vec![0u8; frame_bytes];
        let mut frame_number: i64 = 0;

        loop {
            // Check for shutdown at top of loop
            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown");
                break;
            }

            // Wait for next hardware frame, checking for shutdown on every spin
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

            // Check again right before committing to the barrier
            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown before barrier");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            // Barrier: synchronize with other cameras + gatherer.
            // Returns false if barrier was broken (shutdown in progress).
            if !barrier.wait() {
                tracing::info!("Camera {label}: barrier broken (shutdown)");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            // Check one more time after barrier release
            if check_shutdown(command_receiver) {
                tracing::info!("Camera {label}: shutdown after barrier");
                Cap_closeStream(ctx, stream);
                Cap_releaseContext(ctx);
                return Ok(());
            }

            let grab_timestamp = performance_counter_nanoseconds();
            let result = Cap_captureFrame(ctx, stream, buffer.as_mut_ptr(), frame_bytes as u32);

            if result != CAPRESULT_OK {
                let _ = event_sender.send(CameraEvent::Error(format!(
                    "Camera {label}: captureFrame failed at frame {frame_number} ({})",
                    result_name(result)
                )));
                break;
            }

            let packet = FramePacket {
                data: FrameData::Rgb(buffer.clone()),
                width: actual_width,
                height: actual_height,
                grab_timestamp_nanoseconds: grab_timestamp,
                identity: identity.clone(),
                frame_number,
            };
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

unsafe fn open_camera_stream(
    ctx: CapContext,
    index: u32,
    requested_width: u32,
    requested_height: u32,
    label: &str,
) -> anyhow::Result<(CapStream, u32, u32)> {
    let device_count = unsafe { Cap_getDeviceCount(ctx) };
    if index >= device_count {
        anyhow::bail!("Camera index {index} not found (only {device_count} devices)");
    }

    let num_formats = unsafe { Cap_getNumFormats(ctx, index) };
    if num_formats <= 0 {
        anyhow::bail!("Camera {label}: no formats available");
    }

    let mut chosen_format: Option<CapFormatID> = None;
    let mut chosen_info = CapFormatInfo::default();

    for f in 0..num_formats {
        let mut info = CapFormatInfo::default();
        if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK {
            if info.fourcc == FOURCC_MJPG
                && info.width == requested_width
                && info.height == requested_height
            {
                chosen_format = Some(f as CapFormatID);
                chosen_info = info;
                break;
            }
        }
    }

    if chosen_format.is_none() {
        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if unsafe { Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) } == CAPRESULT_OK
                && info.fourcc == FOURCC_MJPG
            {
                chosen_format = Some(f as CapFormatID);
                chosen_info = info;
                break;
            }
        }
    }

    let format_id = chosen_format
        .ok_or_else(|| anyhow::anyhow!("Camera {label}: no MJPG format found"))?;

    tracing::info!(
        "Camera {label}: format {format_id} ({}x{} @{}fps MJPG)",
        chosen_info.width,
        chosen_info.height,
        chosen_info.fps,
    );

    let stream = unsafe { Cap_openStream(ctx, index, format_id) };
    if stream < 0 {
        anyhow::bail!("Camera {label}: Cap_openStream returned {stream}");
    }

    Ok((stream, chosen_info.width, chosen_info.height))
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

unsafe fn stabilize(ctx: CapContext, stream: CapStream, width: u32, height: u32) {
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
