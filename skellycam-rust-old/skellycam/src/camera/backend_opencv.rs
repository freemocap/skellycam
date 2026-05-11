//! Camera thread using opencv crate with DirectShow backend.
//!
//! DirectShow provides better USB bandwidth multiplexing than MSMF for
//! multi-camera setups — the same backend Python SkellyCam uses.
//!
//! Key decisions:
//! - CAP_DSHOW (not CAP_MSMF) for DirectShow's superior USB arbitration
//! - MJPEG fourcc forced via capture.set() — correct integer-to-f64 cast
//!   (not f64::from_bits, which puts raw IEEE 754 bits into the value)
//! - JPEG bytes extracted directly from the Mat — no BGR→RGB conversion
//!   in the hot path, same as the nokhwa JPEG passthrough approach

use std::sync::mpsc;
use std::thread;

use anyhow::Context;
use opencv::core::Mat;
use opencv::prelude::*;
use opencv::videoio;

use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket};
use crate::timestamps::performance::performance_counter_nanoseconds;

pub fn spawn_camera_thread_opencv(
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

    let camera_label = identity.label();

    thread::spawn(move || {
        let mut capture = match open_camera_dshow(index, requested_width, requested_height) {
            Ok(cap) => cap,
            Err(error) => {
                let _ = event_sender.send(CameraEvent::Error(format!(
                    "Failed to open camera {camera_label}: {error}"
                )));
                return;
            }
        };

        // Resolution from first frame (not from get() which may return 0)
        let mut width: u32 = 0;
        let mut height: u32 = 0;
        let mut frame_number: i64 = 0;
        let mut previous_grab_timestamp: i64 = 0;
        let mut total_grab_interval_nanoseconds: f64 = 0.0;
        let mut total_send_wait_nanoseconds: f64 = 0.0;
        let mut timing_sample_count: u64 = 0;
        let mut frame = Mat::default();

        loop {
            // Phase A: drain commands
            let mut should_shutdown = false;
            loop {
                match command_receiver.try_recv() {
                    Ok(CameraCommand::Shutdown) => {
                        should_shutdown = true;
                        break;
                    }
                    Err(mpsc::TryRecvError::Empty) => break,
                    Err(mpsc::TryRecvError::Disconnected) => {
                        should_shutdown = true;
                        break;
                    }
                }
            }

            if should_shutdown {
                let _ = capture.release();
                tracing::info!("Camera {camera_label} thread exiting.");
                return;
            }

            // Phase B: read frame
            match capture.read(&mut frame) {
                Ok(true) => {
                    if frame_number <= 3 {
                        eprintln!("Camera {camera_label}: read frame {frame_number}");
                    }
                    let grab_timestamp = performance_counter_nanoseconds();

                    if frame_number > 0 {
                        total_grab_interval_nanoseconds +=
                            (grab_timestamp - previous_grab_timestamp) as f64;
                        timing_sample_count += 1;
                    }
                    previous_grab_timestamp = grab_timestamp;

                    // Get resolution from first frame
                    if width == 0 {
                        width = frame.cols() as u32;
                        height = frame.rows() as u32;
                        tracing::info!(
                            "Camera thread started: {camera_label} at {width}x{height}"
                        );
                    }

                    // OpenCV's capture.read() decodes MJPEG to BGR internally.
                    // Extract raw BGR pixels — consumer can convert to RGB if needed.
                    let bgr_bytes = frame.data_bytes().unwrap_or(&[]).to_vec();

                    let packet = FramePacket {
                        data: FrameData::Bgr(bgr_bytes),
                        width,
                        height,
                        grab_timestamp_nanoseconds: grab_timestamp,
                        identity: identity.clone(),
                        frame_number,
                    };

                    frame_number += 1;

                    let send_start = performance_counter_nanoseconds();
                    let send_result = frame_sender.send(packet);
                    let send_end = performance_counter_nanoseconds();
                    total_send_wait_nanoseconds += (send_end - send_start) as f64;

                    if frame_number % 60 == 0 && timing_sample_count > 0 {
                        let avg_interval_ms = total_grab_interval_nanoseconds
                            / timing_sample_count as f64 / 1_000_000.0;
                        let avg_fps = 1_000_000_000.0
                            / (total_grab_interval_nanoseconds / timing_sample_count as f64);
                        let avg_wait_us = total_send_wait_nanoseconds / 60.0 / 1_000.0;

                        eprintln!(
                            "[{unique_id}] {fps:>5.1} fps | grab {grab:>5.0} µs | wait {wait:>5.0} µs",
                            unique_id = identity.unique_identifier,
                            fps = avg_fps,
                            grab = avg_interval_ms * 1_000.0,
                            wait = avg_wait_us,
                        );

                        total_grab_interval_nanoseconds = 0.0;
                        total_send_wait_nanoseconds = 0.0;
                        timing_sample_count = 0;
                    }

                    if send_result.is_err() {
                        let _ = capture.release();
                        return;
                    }
                }
                Ok(false) => continue,
                Err(error) => {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Read error on {camera_label}: {error}"
                    )));
                    continue;
                }
            }
        }
    });

    (handle, event_receiver, frame_receiver)
}

/// Open camera with OpenCV's DirectShow backend, requesting MJPEG format.
fn open_camera_dshow(
    index: u32,
    requested_width: u32,
    requested_height: u32,
) -> anyhow::Result<videoio::VideoCapture> {
    let mut capture = videoio::VideoCapture::new(index as i32, videoio::CAP_DSHOW)
        .context("Failed to open camera with DirectShow")?;

    if !capture.is_opened()? {
        anyhow::bail!("Camera {index} opened but is_opened() returned false.");
    }

    if requested_width > 0 && requested_height > 0 {
        let _ = capture.set(videoio::CAP_PROP_FRAME_WIDTH, requested_width as f64);
        let _ = capture.set(videoio::CAP_PROP_FRAME_HEIGHT, requested_height as f64);
    }
    let _ = capture.set(videoio::CAP_PROP_FPS, 30.0);

    Ok(capture)
}
