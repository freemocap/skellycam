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

        let mut width: u32 = 0;
        let mut height: u32 = 0;
        let mut frame_number: i64 = 0;
        let mut previous_timestamp: i64 = 0;
        let mut total_interval_ns: f64 = 0.0;
        let mut total_wait_ns: f64 = 0.0;
        let mut sample_count: u64 = 0;
        let mut frame = Mat::default();

        loop {
            let mut should_shutdown = false;
            loop {
                match command_receiver.try_recv() {
                    Ok(CameraCommand::Shutdown) => { should_shutdown = true; break; }
                    Err(mpsc::TryRecvError::Empty) => break,
                    Err(mpsc::TryRecvError::Disconnected) => { should_shutdown = true; break; }
                }
            }
            if should_shutdown {
                let _ = capture.release();
                tracing::info!("Camera {label} exiting.");
                return;
            }

            match capture.read(&mut frame) {
                Ok(true) => {
                    let timestamp = performance_counter_nanoseconds();

                    if frame_number > 0 {
                        total_interval_ns += (timestamp - previous_timestamp) as f64;
                        sample_count += 1;
                    }
                    previous_timestamp = timestamp;

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
                        grab_timestamp_nanoseconds: timestamp,
                        identity: identity.clone(),
                        frame_number,
                    };
                    frame_number += 1;

                    let send_start = performance_counter_nanoseconds();
                    let send_result = frame_sender.send(packet);
                    let send_end = performance_counter_nanoseconds();
                    total_wait_ns += (send_end - send_start) as f64;

                    if frame_number % 60 == 0 && sample_count > 0 {
                        let avg_interval_ms = total_interval_ns / sample_count as f64 / 1_000_000.0;
                        let fps = 1_000_000_000.0 / (total_interval_ns / sample_count as f64);
                        let wait_us = total_wait_ns / 60.0 / 1_000.0;
                        eprintln!(
                            "[{id}] {fps:>5.1} fps | grab {grab:>5.0} µs | wait {wait_us:>5.0} µs",
                            id = identity.unique_identifier,
                            grab = avg_interval_ms * 1_000.0,
                        );
                        total_interval_ns = 0.0;
                        total_wait_ns = 0.0;
                        sample_count = 0;
                    }

                    if send_result.is_err() {
                        let _ = capture.release();
                        return;
                    }
                }
                Ok(false) => continue,
                Err(error) => {
                    let _ = event_sender.send(CameraEvent::Error(format!(
                        "Read error on {label}: {error}"
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
) -> anyhow::Result<videoio::VideoCapture> {
    // Try CAP_ANY — let OpenCV pick the best backend
    let mut capture = videoio::VideoCapture::new(index as i32, videoio::CAP_DSHOW)
        .context("Failed to open camera with DirectShow")?;

    if !capture.is_opened()? {
        anyhow::bail!("Camera {index} opened but is_opened() returned false.");
    }

    // Match Python SkellyCam's property-setting order exactly:
    // FOURCC → WIDTH → HEIGHT → FPS → BUFFERSIZE
    // DirectShow respects this order; MSMF ignores FOURCC and BUFFERSIZE.
    let mjpeg = 0x47504A4Du32 as f64; // fourcc('M','J','P','G')
    let _ = capture.set(videoio::CAP_PROP_FOURCC, mjpeg);

    if requested_width > 0 {
        let _ = capture.set(videoio::CAP_PROP_FRAME_WIDTH, requested_width as f64);
        let _ = capture.set(videoio::CAP_PROP_FRAME_HEIGHT, requested_height as f64);
    }
    let _ = capture.set(videoio::CAP_PROP_FPS, 30.0);

    // BUFFERSIZE=1: only buffer 1 frame — reduces latency, required for
    // some DirectShow drivers to apply other property changes.
    let _ = capture.set(videoio::CAP_PROP_BUFFERSIZE, 1.0);

    let actual_w = capture.get(videoio::CAP_PROP_FRAME_WIDTH).unwrap_or(-1.0);
    let actual_h = capture.get(videoio::CAP_PROP_FRAME_HEIGHT).unwrap_or(-1.0);
    let fourcc = capture.get(videoio::CAP_PROP_FOURCC).unwrap_or(-1.0) as u32;
    eprintln!(
        "Camera {index}: {actual_w}x{actual_h} fourcc=0x{fourcc:08X}"
    );

    Ok(capture)
}
