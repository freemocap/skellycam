//! Dispatcher thread — the single downstream consumer of `MultiFramePayload`.
//!
//! Spawned by `CameraGroup::start()`. Receives multiframes from the gatherer
//! via an unbounded channel, processes them, and stores the encoded frontend
//! payload for external polling.
//!
//! When recording is active, also feeds per-camera MJPEG frames to ffmpeg
//! (VideoRecorder) and writes per-frame timestamp CSV rows (CsvWriter).
//!
//! Spin-waits on both the multiframe channel and the control channel — never
//! blocks on either, so config changes and recording commands are responsive.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::camera::MultiFramePayload;
use crate::camera_group::frontend_encoder::encode_multiframe;
use crate::camera_group::jpeg_transform::rotate_jpeg_lossless;
use crate::recording::VideoRecorder;
use crate::timestamps::CsvWriter;

use super::types::DispatcherCommand;

// ── Frontend payload type ─────────────────────────────────────────────────

/// Encoded frontend payload, ready for polling by external consumers.
///
/// Stored in an `Arc<Mutex<Option<...>>>` shared between the dispatcher
/// thread (writer) and the `CameraGroup` handle (reader).
#[derive(Clone)]
pub struct FrontendPayload {
    pub frame_number: i64,
    pub timestamp_ns: f64,
    pub jpeg_bytes: Vec<u8>,
}

// ── Dispatcher spawn ────────────────────────────────────────────────────────

/// Spawn the dispatcher thread.
///
/// # Arguments
///
/// * `multi_frame_receiver` — Unbounded receiver from the gatherer.
/// * `control_receiver` — Receives recording/configure/shutdown commands.
/// * `latest_payload` — Shared slot for the latest encoded frontend payload.
/// * `recording_active` — Shared flag, set true while recording.
pub fn spawn_dispatcher(
    multi_frame_receiver: Receiver<MultiFramePayload>,
    control_receiver: Receiver<DispatcherCommand>,
    latest_payload: Arc<Mutex<Option<FrontendPayload>>>,
    recording_active: Arc<AtomicBool>,
) -> JoinHandle<()> {
    thread::spawn(move || {
        // Recording state (only Some while recording)
        let mut video_recorders: Option<Vec<VideoRecorder>> = None;
        let mut csv_writers: Option<Vec<CsvWriter>> = None;

        loop {
            // ── Drain all pending commands (always responsive) ──
            while let Ok(cmd) = control_receiver.try_recv() {
                match cmd {
                    DispatcherCommand::StartRecording { params } => {
                        // Placeholder — wired in a later step
                        eprintln!(
                            "[dispatcher] recording started → {}",
                            params.output_dir
                        );
                        recording_active.store(true, Ordering::SeqCst);
                    }
                    DispatcherCommand::StopRecording { response_tx } => {
                        recording_active.store(false, Ordering::SeqCst);
                        // Placeholder — finalize recorders
                        let _ = response_tx.send(crate::recording::finalizer::RecordingSummary {
                            total_frames_per_camera: 0,
                            video_paths: Vec::new(),
                            csv_paths: Vec::new(),
                            info_json_path: std::path::PathBuf::new(),
                        });
                        eprintln!("[dispatcher] recording stopped");
                    }
                    DispatcherCommand::Shutdown => {
                        eprintln!("[dispatcher] shutting down");
                        return;
                    }
                }
            }

            // ── Try to receive the next multiframe ──
            match multi_frame_receiver.try_recv() {
                Ok(mut payload) => {
                    // Apply lossless JPEG rotation per frame
                    for frame in &mut payload.frames {
                        if frame.rotation != -1 {
                            if let FrameData::Mjpg(ref jpeg_bytes) = frame.data {
                                if let Some(rotated) = rotate_jpeg_lossless(jpeg_bytes, frame.rotation) {
                                    frame.data = FrameData::Mjpg(rotated);
                                }
                            }
                        }
                    }

                    // Encode for frontend
                    match encode_multiframe(&payload) {
                        Ok(binary) => {
                            let timestamp_ns = if payload.frames.is_empty() {
                                0.0
                            } else {
                                let sum: i64 = payload
                                    .frames
                                    .iter()
                                    .map(|f| f.timestamps.frame_available_ns)
                                    .sum();
                                (sum as f64) / (payload.frames.len() as f64)
                            };
                            let frame_number = payload
                                .frames
                                .first()
                                .map(|f| f.frame_number)
                                .unwrap_or(0);

                            if let Ok(mut guard) = latest_payload.lock() {
                                *guard = Some(FrontendPayload {
                                    frame_number,
                                    timestamp_ns,
                                    jpeg_bytes: binary,
                                });
                            }
                        }
                        Err(e) => {
                            tracing::error!("[dispatcher] encode error: {e}");
                        }
                    }

                    // ── Recording: feed per-camera frames ──
                    if recording_active.load(Ordering::SeqCst) {
                        if let (Some(recorders), Some(writers)) =
                            (video_recorders.as_mut(), csv_writers.as_mut())
                        {
                            for (i, frame) in payload.frames.iter().enumerate() {
                                if let (Some(recorder), Some(writer)) =
                                    (recorders.get_mut(i), writers.get_mut(i))
                                {
                                    let bytes = frame.data.as_bytes();
                                    let now = crate::timestamps::performance::performance_counter_nanoseconds();
                                    if let Err(e) = recorder.feed_frame(
                                        bytes,
                                        frame.frame_number,
                                        frame.timestamps.frame_available_ns,
                                        now,
                                    ) {
                                        tracing::error!(
                                            "[dispatcher] recorder error for camera {i}: {e}"
                                        );
                                    }
                                    if let Err(e) = writer.write_row(
                                        frame.frame_number,
                                        &frame.timestamps,
                                    ) {
                                        tracing::error!(
                                            "[dispatcher] CSV write error for camera {i}: {e}"
                                        );
                                    }
                                }
                            }
                        }
                    }
                }
                Err(mpsc::TryRecvError::Empty) => {
                    // No frame ready — brief sleep to avoid busy-waiting
                    std::thread::sleep(Duration::from_millis(1));
                }
                Err(mpsc::TryRecvError::Disconnected) => {
                    eprintln!("[dispatcher] gatherer disconnected, exiting");
                    break;
                }
            }
        }
    })
}

use crate::camera::FrameData;