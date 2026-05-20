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
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::camera::{CameraIdentity, MultiFramePayload};
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

/// Per-camera raw frame data — JPEG bytes with metadata, stored for on-demand
/// decoding by downstream consumers (tests, PyO3 bridge, image analysis).
///
/// The dispatcher clones these into a shared slot each multiframe. Decoding
/// happens only when a consumer calls `mjpeg_to_rgb()` — never on the hot path.
#[derive(Clone)]
pub struct RawFrame {
    pub camera_id: String,
    pub camera_index: i32,
    pub width: u32,
    pub height: u32,
    pub jpeg_bytes: Vec<u8>,
}

// ── Dispatcher spawn ────────────────────────────────────────────────────────

/// Spawn the dispatcher thread.
pub fn spawn_dispatcher(
    multi_frame_receiver: Receiver<MultiFramePayload>,
    control_receiver: Receiver<DispatcherCommand>,
    latest_payload: Arc<Mutex<Option<FrontendPayload>>>,
    latest_raw_frames: Arc<Mutex<Option<Vec<RawFrame>>>>,
    recording_active: Arc<AtomicBool>,
) -> JoinHandle<()> {
    thread::Builder::new()
        .name("dispatcher".into())
        .spawn(move || {
        // Recording state (only Some while recording)
        let mut video_recorders: Option<Vec<VideoRecorder>> = None;
        let mut csv_writers: Option<Vec<CsvWriter>> = None;
        let mut recording_stats: Option<RecordingStats> = None;
        let mut pending_recording: Option<super::types::RecordingParams> = None;
        let mut recording_dir: Option<PathBuf> = None;
        let mut camera_infos: Option<Vec<(CameraIdentity, u32, u32)>> = None;

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
                            recording_dir.take(),
                            camera_infos.take(),
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
                                recording_dir.take(),
                                camera_infos.take(),
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
                    static DISPATCH_COUNT: AtomicU64 = AtomicU64::new(0);
                    let count = DISPATCH_COUNT.fetch_add(1, Ordering::Relaxed) + 1;
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
                            Ok((recorders, writers, session_dir, infos)) => {
                                let camera_count = payload.frames.len();
                                let dir_display = session_dir.display().to_string();
                                recording_stats = Some(RecordingStats::new(camera_count));
                                video_recorders = Some(recorders);
                                csv_writers = Some(writers);
                                recording_dir = Some(session_dir);
                                camera_infos = Some(infos);
                                recording_active.store(true, Ordering::SeqCst);
                                tracing::info!(
                                    "[dispatcher] recording started → {dir_display} ({camera_count} cameras)",
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

                    // ── Store raw per-camera JPEGs for on-demand decode ──
                    if let Ok(mut guard) = latest_raw_frames.lock() {
                        *guard = Some(
                            payload
                                .frames
                                .iter()
                                .map(|f| RawFrame {
                                    camera_id: f.identity.camera_id.clone(),
                                    camera_index: f.identity.camera_index,
                                    width: f.width,
                                    height: f.height,
                                    jpeg_bytes: f.data.as_bytes().to_vec(),
                                })
                                .collect(),
                        );
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
    .expect("Failed to spawn dispatcher thread")
}

// ── Recording lifecycle helpers ────────────────────────────────────────────

/// Create per-camera `VideoRecorder` and `CsvWriter` from the first multiframe.
///
/// Creates a timestamped session subdirectory inside `params.output_dir`,
/// then sets up per-camera video and CSV files inside it.
/// Returns the recorders, writers, session directory path, and camera identity
/// info needed by the finalizer.
fn create_recorders(
    params: &super::types::RecordingParams,
    payload: &MultiFramePayload,
) -> anyhow::Result<(
    Vec<VideoRecorder>,
    Vec<CsvWriter>,
    PathBuf,
    Vec<(CameraIdentity, u32, u32)>,
)> {
    use crate::recording::VideoRecorderConfig;

    let session_name = {
        let now = chrono::Local::now();
        let gmt_offset = now.offset().local_minus_utc() / 3600;
        let base = now.format("%Y-%m-%dT%H_%M_%S").to_string();
        let tag = params.label.as_deref().unwrap_or("recording");
        format!("{base}_gmt{gmt_offset:+}_{tag}")
    };
    let output_dir = PathBuf::from(&params.output_dir);
    let session_dir = output_dir.join(&session_name);
    let label = params.label.as_deref().unwrap_or("recording");
    let videos_dir = session_dir.join("synchronized_videos");
    let timestamps_dir = videos_dir.join("timestamps").join("camera_timestamps");
    fs::create_dir_all(&videos_dir)?;
    fs::create_dir_all(&timestamps_dir)?;

    let mut recorders = Vec::with_capacity(payload.frames.len());
    let mut writers = Vec::with_capacity(payload.frames.len());
    let mut infos: Vec<(CameraIdentity, u32, u32)> =
        Vec::with_capacity(payload.frames.len());

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
        infos.push((identity.clone(), frame.width, frame.height));
    }

    Ok((recorders, writers, session_dir, infos))
}

/// Finalize all recorders, compute stats, and build the recording summary.
///
/// Finishes each recorder and CSV writer, then delegates to
/// `finalizer::finalize_recording()` which validates frame counts across
/// cameras and writes `recording_info.json`.
fn finalize_recording_session(
    video_recorders: &mut Option<Vec<VideoRecorder>>,
    csv_writers: &mut Option<Vec<CsvWriter>>,
    recording_stats: Option<RecordingStats>,
    recording_dir: Option<PathBuf>,
    camera_infos: Option<Vec<(CameraIdentity, u32, u32)>>,
) -> finalizer::RecordingSummary {
    let stats = recording_stats.map(|s| s.finalize());

    // Default empty summary in case recorders were never created
    let empty_summary = finalizer::RecordingSummary {
        total_frames_per_camera: 0,
        video_paths: Vec::new(),
        csv_paths: Vec::new(),
        info_json_path: PathBuf::new(),
        stats: stats.clone(),
    };

    let (Some(recorders), Some(writers), Some(session_dir), Some(infos)) = (
        video_recorders.take(),
        csv_writers.take(),
        recording_dir,
        camera_infos,
    ) else {
        return empty_summary;
    };

    let mut video_paths = Vec::with_capacity(recorders.len());
    let mut csv_paths = Vec::with_capacity(writers.len());

    for recorder in recorders {
        let frame_count = recorder.frame_count();
        let path = recorder.output_path().to_path_buf();
        match recorder.finish() {
            Ok(timestamps) => {
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

    if infos.len() != video_paths.len() || infos.len() != csv_paths.len() {
        tracing::error!(
            "[dispatcher] mismatch: {} camera infos, {} videos, {} CSVs — skipping recording_info.json",
            infos.len(),
            video_paths.len(),
            csv_paths.len(),
        );
        return finalizer::RecordingSummary {
            total_frames_per_camera: 0,
            video_paths,
            csv_paths,
            info_json_path: PathBuf::new(),
            stats,
        };
    }

    let total = video_paths.len() as u64;
    match finalizer::finalize_recording(
        &session_dir,
        &infos,
        &video_paths,
        &csv_paths,
        stats,
    ) {
        Ok(summary) => {
            tracing::info!(
                "[dispatcher] recording_info.json written → {}",
                summary.info_json_path.display(),
            );
            summary
        }
        Err(e) => {
            tracing::error!("[dispatcher] finalize_recording error: {e}");
            finalizer::RecordingSummary {
                total_frames_per_camera: total,
                video_paths,
                csv_paths,
                info_json_path: PathBuf::new(),
                stats: None,
            }
        }
    }
}

use crate::camera::FrameData;
