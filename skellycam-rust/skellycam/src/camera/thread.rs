//! Camera thread: OpenCV DirectShow capture.

use std::sync::mpsc;
use std::thread;

use anyhow::Context;
use opencv::core::Mat;
use opencv::prelude::*;
use opencv::videoio;

use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket};
use crate::timestamps::performance::performance_counter_nanoseconds;

pub fn spawn_camera_thread(
    index: u32,
    requested_width: u32,
    requested_height: u32,
    identity: CameraIdentity,
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
        width: 0,
        height: 0,
    };

    let label = identity.label();

    thread::spawn(move || {
        let mut capture = match open_camera(index, requested_width, requested_height) {
            Ok(cap) => cap,
            Err(error) => {
                let _ = event_sender.send(CameraEvent::Error(format!(
                    "Failed to open camera {label}: {error}"
                )));
                return;
            }
        };

        const MAX_FAIL_COUNT: u32 = 30;

        let mut width: u32 = 0;
        let mut height: u32 = 0;
        let mut frame_number: i64 = 0;
        let mut previous_timestamp: i64 = 0;
        let mut total_interval_ns: f64 = 0.0;
        let mut total_read_ns: f64 = 0.0;
        let mut total_wait_ns: f64 = 0.0;
        let mut sample_count: u64 = 0;
        let mut fail_count: u32 = 0;
        let mut frame = Mat::default();

        loop {
            loop {
                match command_receiver.try_recv() {
                    Ok(CameraCommand::Shutdown) => {
                        let _ = capture.release();
                        tracing::info!("Camera {label} exiting.");
                        return;
                    }
                    Err(mpsc::TryRecvError::Empty) => break,
                    Err(mpsc::TryRecvError::Disconnected) => {
                        let _ = capture.release();
                        tracing::info!("Camera {label} exiting (disconnected).");
                        return;
                    }
                }
            }

            // --- read: combined grab+retrieve (using read() because separate
            //     grab()/retrieve_def() showed 53ms retrieve times on some systems) ---
            let pre_grab = performance_counter_nanoseconds();
            match capture.read(&mut frame) {
                Ok(true) => {}
                Ok(false) => {
                    fail_count += 1;
                    tracing::warn!("Camera {label}: read returned false (fail {fail_count}/{MAX_FAIL_COUNT})");
                    if fail_count >= MAX_FAIL_COUNT {
                        let _ = event_sender.send(CameraEvent::Error(format!(
                            "Too many read misses on {label}"
                        )));
                        let _ = capture.release();
                        return;
                    }
                    continue;
                }
                Err(error) => {
                    fail_count += 1;
                    tracing::warn!("Camera {label}: read error (fail {fail_count}/{MAX_FAIL_COUNT}): {error}");
                    if fail_count >= MAX_FAIL_COUNT {
                        let _ = event_sender.send(CameraEvent::Error(format!(
                            "Too many read failures on {label}: {error}"
                        )));
                        let _ = capture.release();
                        return;
                    }
                    continue;
                }
            };
            let post_retrieve = performance_counter_nanoseconds();

            // Success — reset fail counter
            fail_count = 0;

            if frame_number > 0 {
                total_interval_ns += (pre_grab - previous_timestamp) as f64;
                sample_count += 1;
            }
            previous_timestamp = pre_grab;

            total_read_ns += (post_retrieve - pre_grab) as f64;

            if width == 0 {
                width = frame.cols() as u32;
                height = frame.rows() as u32;
                tracing::info!("Camera {label}: {width}x{height}");
            }

            let bgr = frame.data_bytes().unwrap_or(&[]).to_vec();

            let packet = FramePacket {
                data: FrameData::Bgr(bgr),
                width,
                height,
                grab_timestamp_nanoseconds: pre_grab,
                identity: identity.clone(),
                frame_number,
            };
            frame_number += 1;

            let send_start = performance_counter_nanoseconds();
            let send_result = frame_sender.send(packet);
            let send_end = performance_counter_nanoseconds();
            total_wait_ns += (send_end - send_start) as f64;

            if frame_number % 60 == 0 && sample_count > 0 {
                let fps = 1_000_000_000.0 / (total_interval_ns / sample_count as f64);
                let read_us = total_read_ns / 60.0 / 1_000.0;
                let wait_us = total_wait_ns / 60.0 / 1_000.0;
                eprintln!(
                    "[{id}] {fps:>5.1} fps | read {read_us:>6.0} µs | wait {wait_us:>5.0} µs",
                    id = identity.unique_identifier,
                );
                total_interval_ns = 0.0;
                total_read_ns = 0.0;
                total_wait_ns = 0.0;
                sample_count = 0;
            }

            if send_result.is_err() {
                let _ = capture.release();
                return;
            }
        }
    });

    (handle, event_receiver, frame_receiver)
}

// decode_fourcc is now in super::decode_fourcc (camera/mod.rs)

fn open_camera(
    index: u32,
    requested_width: u32,
    requested_height: u32,
) -> anyhow::Result<videoio::VideoCapture> {
    let mut capture = videoio::VideoCapture::new(index as i32, videoio::CAP_DSHOW)
        .context("Failed to open camera with DirectShow")?;

    if !capture.is_opened()? {
        anyhow::bail!("Camera {index} opened but is_opened() returned false.");
    }

    let mjpeg = 0x47504A4Du32 as f64; // fourcc('M','J','P','G')

    // --- Phase A: pre-read config (matching Python create_cv2_video_capture) ---
    let _ = capture.set(videoio::CAP_PROP_FOURCC, mjpeg);
    if requested_width > 0 {
        let _ = capture.set(videoio::CAP_PROP_FRAME_WIDTH, requested_width as f64);
        let _ = capture.set(videoio::CAP_PROP_FRAME_HEIGHT, requested_height as f64);
    }
    let _ = capture.set(videoio::CAP_PROP_BUFFERSIZE, 1.0);

    // --- Warmup read: starts the DirectShow streaming graph ---
    let mut warmup = Mat::default();
    let read_ok = capture.read(&mut warmup)?;
    let warmup_size = if read_ok { warmup.size().unwrap_or_default() } else { opencv::core::Size::default() };

    // --- Phase B: post-read config ---
    // FOURCC must be set AGAIN after the first read().
    // Do NOT re-set W/H here — changing resolution after the graph
    // is running can trigger a media type renegotiation that resets
    // the FOURCC back to the camera's default.
    let _ = capture.set(videoio::CAP_PROP_FOURCC, mjpeg);

    // --- Read back actual config ---
    let actual_w = capture.get(videoio::CAP_PROP_FRAME_WIDTH).unwrap_or(-1.0);
    let actual_h = capture.get(videoio::CAP_PROP_FRAME_HEIGHT).unwrap_or(-1.0);
    let fourcc_val = capture.get(videoio::CAP_PROP_FOURCC).unwrap_or(-1.0) as u32;
    let fourcc_str = super::decode_fourcc(fourcc_val);
    let actual_fps = capture.get(videoio::CAP_PROP_FPS).unwrap_or(-1.0);
    let backend = capture
        .get_backend_name()
        .unwrap_or_else(|_| "unknown".to_string());

    eprintln!();
    eprintln!("╔══════════════════════════════════════════╗");
    eprintln!("║  CAMERA {index} CONFIG                       ║", );
    eprintln!("╠══════════════════════════════════════════╣");
    eprintln!("║  BACKEND:  {backend:<30} ║");
    eprintln!("║  FOURCC:   {fourcc_str:<30} ║");
    eprintln!("║  FOURCC hex: 0x{fourcc_val:08X}                  ║");
    eprintln!("║  RESOLUTION: {actual_w}x{actual_h:<30} ║");
    eprintln!("║  FPS:       {actual_fps:<30} ║");
    eprintln!("║  WARMUP:    ok={read_ok}  {warmup_w}x{warmup_h}              ║",
        warmup_w = warmup_size.width,
        warmup_h = warmup_size.height,
    );
    eprintln!("╚══════════════════════════════════════════╝");
    eprintln!();

    Ok(capture)
}
