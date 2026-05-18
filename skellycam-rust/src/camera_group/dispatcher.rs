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

use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::camera::MultiFramePayload;
use crate::camera_group::frontend_encoder::encode_multiframe;
use crate::camera_group::jpeg_transform::rotate_jpeg_lossless;
use crate::camera_group::recording_stats::RecordingStats;
use crate::recording::finalizer;
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
        let mut recording_stats: Option<RecordingStats> = None;
        let mut pending_recording: Option<super::types::RecordingParams> = None;

        loop {
            // ── Drain all pending commands ──
            while let Ok(cmd) = control_receiver.try_recv() {
                match cmd {
                    DispatcherCommand::StartRecording { params } => {
                        tracing::info!(
                            "[dispatcher] recording queued → {}",
                            params.output_dir
                        );
                        pending_recording = Some(params);
                    }
                    DispatcherCommand::StopRecording { response_tx } => {
                        recording_active.store(false, Ordering::SeqCst);
                        let summary = finalize_recording_session(
                            &mut video_recorders,
                            &mut csv_writers,
                            recording_stats.take(),
                        );
                        let _ = response_tx.send(summary);
                        tracing::info!("[dispatcher] recording stopped");
                    }
                    DispatcherCommand::Shutdown => {
                        // Clean up any in-progress recording
                        if recording_active.load(Ordering::SeqCst) {
                            recording_active.store(false, Ordering::SeqCst);
                            let _ = finalize_recording_session(
                                &mut video_recorders,
                                &mut csv_writers,
                                recording_stats.take(),
                            );
                        }
                        tracing::info!("[dispatcher] shutting down");
                        return;
                    }
                }
            }

            // ── Try to receive the next multiframe ──
            match multi_frame_receiver.try_recv() {
                Ok(mut payload) => {
                    static mut DISPATCH_COUNT: u64 = 0;
                    let count = unsafe { DISPATCH_COUNT += 1; DISPATCH_COUNT };
                    tracing::trace!(
                        "[DISPATCH mf#{count}] received {} frames",
                        payload.frames.len(),
                    );

                    // ── Deferred recorder creation (first multiframe after StartRecording) ──
                    if pending_recording.is_some() {
                        let params = pending_recording.take().unwrap();
                        match create_recorders(
                            &params,
                            &payload,
                        ) {
                            Ok((recorders, writers)) => {
                                let camera_count = payload.frames.len();
                                recording_stats = Some(RecordingStats::new(camera_count));
                                video_recorders = Some(recorders);
                                csv_writers = Some(writers);
                                recording_active.store(true, Ordering::SeqCst);
                                tracing::info!(
                                    "[dispatcher] recording started → {} ({} cameras)",
                                    params.output_dir, camera_count,
                                );
                            }
                            Err(e) => {
                                tracing::error!(
                                    "[dispatcher] failed to create recorders: {e}"
                                );
                                recording_active.store(false, Ordering::SeqCst);
                            }
                        }
                    }

                    // Apply lossless JPEG rotation per frame
                    for frame in &mut payload.frames {
                        if frame.rotation != -1 {
                            if let FrameData::Mjpg(ref jpeg_bytes) = frame.data {
                                if let Some(rotated) =
                                    rotate_jpeg_lossless(jpeg_bytes, frame.rotation)
                                {
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
                        let post_encode_ns =
                            crate::timestamps::performance::performance_counter_nanoseconds();

                        if let (Some(recorders), Some(writers), Some(stats)) = (
                            video_recorders.as_mut(),
                            csv_writers.as_mut(),
                            recording_stats.as_mut(),
                        ) {
                            for (i, frame) in payload.frames.iter().enumerate() {
                                if let (Some(recorder), Some(writer)) =
                                    (recorders.get_mut(i), writers.get_mut(i))
                                {
                                    let bytes = frame.data.as_bytes();
                                    let now =
                                        crate::timestamps::performance::performance_counter_nanoseconds();
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
                            stats.push_multiframe(&payload, post_encode_ns);
                        }
                    }
                }
                Err(mpsc::TryRecvError::Empty) => {
                    std::thread::sleep(Duration::from_millis(1));
                }
                Err(mpsc::TryRecvError::Disconnected) => {
                    tracing::warn!("[dispatcher] gatherer disconnected, exiting");
                    break;
                }
            }
        }
    })
}

// ── Recording lifecycle helpers ────────────────────────────────────────────

/// Create per-camera `VideoRecorder` and `CsvWriter` from the first multiframe.
fn create_recorders(
    params: &super::types::RecordingParams,
    payload: &MultiFramePayload,
) -> anyhow::Result<(Vec<VideoRecorder>, Vec<CsvWriter>)> {
    use crate::recording::VideoRecorderConfig;

    let output_dir = PathBuf::from(&params.output_dir);
    let label = params.label.as_deref().unwrap_or("recording");
    let videos_dir = output_dir.join("synchronized_videos");
    let timestamps_dir = videos_dir.join("timestamps").join("camera_timestamps");
    fs::create_dir_all(&videos_dir)?;
    fs::create_dir_all(&timestamps_dir)?;

    let mut recorders = Vec::with_capacity(payload.frames.len());
    let mut writers = Vec::with_capacity(payload.frames.len());

    for frame in &payload.frames {
        let identity = &frame.identity;
        let camera_label = format!(
            "Camera_{}_{}",
            identity.camera_index,
            identity.camera_id
        );
        let video_path = videos_dir.join(format!("{camera_label}_{label}.mp4"));
        let csv_path = timestamps_dir.join(format!("{camera_label}_timestamps.csv"));

        let recorder = VideoRecorder::new(
            video_path,
            identity,
            frame.width,
            frame.height,
            30.0, // target FPS for ffmpeg
            &VideoRecorderConfig::default(),
        )?;

        let csv_writer = CsvWriter::new(csv_path)?;

        recorders.push(recorder);
        writers.push(csv_writer);
    }

    Ok((recorders, writers))
}

/// Finalize all recorders, compute stats, and build the recording summary.
fn finalize_recording_session(
    video_recorders: &mut Option<Vec<VideoRecorder>>,
    csv_writers: &mut Option<Vec<CsvWriter>>,
    recording_stats: Option<RecordingStats>,
) -> finalizer::RecordingSummary {
    let stats = recording_stats.map(|s| s.finalize());

    // Default empty summary in case recorders were never created
    let mut summary = finalizer::RecordingSummary {
        total_frames_per_camera: 0,
        video_paths: Vec::new(),
        csv_paths: Vec::new(),
        info_json_path: PathBuf::new(),
        stats,
    };

    if let (Some(recorders), Some(writers)) = (video_recorders.take(), csv_writers.take()) {
        let mut video_paths = Vec::with_capacity(recorders.len());
        let mut csv_paths = Vec::with_capacity(writers.len());
        let mut frame_counts = Vec::with_capacity(recorders.len());

        for recorder in recorders {
            let frame_count = recorder.frame_count();
            let path = recorder.output_path().to_path_buf();
            match recorder.finish() {
                Ok(timestamps) => {
                    frame_counts.push(frame_count);
                    video_paths.push(path);
                    tracing::info!(
                        "[dispatcher] recorder finished: {frame_count} frames, {} timestamps",
                        timestamps.len()
                    );
                }
                Err(e) => {
                    tracing::error!("[dispatcher] recorder finish error: {e}");
                }
            }
        }

        for writer in writers {
            match writer.finish() {
                Ok(path) => {
                    csv_paths.push(path);
                }
                Err(e) => {
                    tracing::error!("[dispatcher] CSV finish error: {e}");
                }
            }
        }

        let total = frame_counts.first().copied().unwrap_or(0);
        summary.total_frames_per_camera = total;
        summary.video_paths = video_paths;
        summary.csv_paths = csv_paths;
    }

    summary
}

use crate::camera::FrameData;
