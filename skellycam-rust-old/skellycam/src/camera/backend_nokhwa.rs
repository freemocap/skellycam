//! Camera thread using nokhwa 
//!
//! Key performance decision for multi-camera sync -  extract raw JPEG bytes from `buffer.buffer()` and send them
//! through the channel. We do NOT decode the jpeg bytes into an image in the hot loop, we can decode downstream as needed.
//! This bypasses MSMF's hardware MFT decoder limit — each camera thread only grabs compressed MJPEG bytes from the driver,
//! with no hardware decode involvement. Software decode happens downstream outside of the fast camera loop.

use std::sync::mpsc;
use std::thread;

use anyhow::Context;
use nokhwa::pixel_format::RgbFormat;
use nokhwa::utils::{
    ApiBackend, CameraIndex, RequestedFormat, RequestedFormatType, Resolution,
};
use nokhwa::Camera;

use super::types::{CameraCommand, CameraEvent, CameraHandle, CameraIdentity, FrameData, FramePacket};
use crate::timestamps::performance::performance_counter_nanoseconds;

pub fn spawn_camera_thread_nokhwa(
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
        let mut camera = match open_camera(index, requested_width, requested_height, &camera_label) {
            Ok(cam) => cam,
            Err(error) => {
                let _ = event_sender.send(CameraEvent::Error(format!(
                    "Failed to open camera {camera_label}: {error}"
                )));
                return;
            }
        };

        let resolution = camera.resolution();
        let width = resolution.width();
        let height = resolution.height();
        tracing::info!("Camera thread started: {camera_label} at {width}x{height}");

        let mut frame_number: i64 = 0;
        let mut previous_grab_timestamp: i64 = 0;
        let mut total_grab_interval_nanoseconds: f64 = 0.0;
        let mut total_send_wait_nanoseconds: f64 = 0.0;
        let mut timing_sample_count: u64 = 0;

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
                let _ = camera.stop_stream();
                tracing::info!("Camera {camera_label} thread exiting.");
                return;
            }

            // Phase B: grab raw frame
            // We call camera.frame() which returns a Buffer with the raw MJPEG bytes.
            // We do NOT call buffer.decode_image() — this is the key difference
            // from the test app. Skipping hardware decode avoids MSMF's MFT instance
            // limit, enabling 6+ cameras without resource exhaustion.
            match camera.frame() {
                Ok(buffer) => {
                    let grab_timestamp = performance_counter_nanoseconds();

                    if frame_number > 0 {
                        total_grab_interval_nanoseconds +=
                            (grab_timestamp - previous_grab_timestamp) as f64;
                        timing_sample_count += 1;
                    }
                    previous_grab_timestamp = grab_timestamp;

                    let jpeg_bytes = buffer.buffer().to_vec();
                    let resolution = buffer.resolution();

                    let packet = FramePacket {
                        data: FrameData::Jpeg(jpeg_bytes),
                        width: resolution.width(),
                        height: resolution.height(),
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
                        let _ = camera.stop_stream();
                        return;
                    }
                }
                Err(error) => {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Capture error on {camera_label}: {error}"
                    )));
                    continue;
                }
            }
        }
    });

    (handle, event_receiver, frame_receiver)
}

fn open_camera(
    index: u32,
    requested_width: u32,
    requested_height: u32,
    label: &str,
) -> anyhow::Result<Camera> {
    let requested = if requested_width > 0 && requested_height > 0 {
        RequestedFormat::new::<RgbFormat>(
            RequestedFormatType::HighestResolution(Resolution::new(
                requested_width,
                requested_height,
            )),
        )
    } else {
        RequestedFormat::new::<RgbFormat>(RequestedFormatType::AbsoluteHighestFrameRate)
    };

    let mut camera = Camera::new(CameraIndex::Index(index), requested)
        .context("Failed to create camera handle")?;

    camera
        .open_stream()
        .context("Failed to start camera stream")?;

    let res = camera.resolution();
    tracing::info!("Camera {label} opened: {}x{}", res.width(), res.height());
    Ok(camera)
}