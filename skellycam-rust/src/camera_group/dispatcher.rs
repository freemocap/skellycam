//! Dispatcher thread — the single downstream consumer of `MultiFramePayload`.
//!
//! Spawned by `CameraGroup::start()`. Receives multiframes from the gatherer
//! via an unbounded channel, processes them, and stores the encoded frontend
//! payload for external polling.
//!
//! When recording is active, per-camera JPEG frames are extracted and sent
//! via an unbounded channel to a dedicated recording thread — so the dispatcher
//! never blocks on ffmpeg pipe writes or CSV fsyncs.
//!
//! Spin-waits on the multiframe channel, the control channel, AND the recording
//! channel — never blocks, so config changes and recording commands stay responsive.

use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::camera::{CameraIdentity, MultiFramePayload};
use crate::camera_group::frontend_encoder::encode_multiframe;
use crate::camera_group::jpeg_transform::rotate_jpeg_lossless;
use crate::camera_group::recording_stats::RecordingStats;
use crate::recording::finalizer::RecordingSummary;
use crate::recording::{
    RecordingFrameData, RecordingHandle, VideoRecorder, spawn_recording_thread,
};
use crate::timestamps::CsvWriter;

use super::types::{DispatcherCommand, SharedConfigMap};

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
    mut shared_configs: SharedConfigMap,
) -> JoinHandle<()> {
    thread::Builder::new()
        .name("dispatcher".into())
        .spawn(move || {
        // Recording state (only Some while recording)
        let mut recording_handle: Option<RecordingHandle> = None;
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
                        let stats_summary = recording_stats.take().map(|s| s.finalize());
                        let summary = if let Some(handle) = recording_handle.take() {
                            match handle.stop(stats_summary) {
                                Ok(s) => s,
                                Err(e) => {
                                    tracing::error!(
                                        "[dispatcher] recording thread stop error: {e}"
                                    );
                                    RecordingSummary {
                                        total_frames_per_camera: 0,
                                        video_paths: Vec::new(),
                                        csv_paths: Vec::new(),
                                        info_json_path: PathBuf::new(),
                                        stats: None,
                                    }
                                }
                            }
                        } else {
                            tracing::warn!(
                                "[dispatcher] StopRecording but no recording handle"
                            );
                            RecordingSummary {
                                total_frames_per_camera: 0,
                                video_paths: Vec::new(),
                                csv_paths: Vec::new(),
                                info_json_path: PathBuf::new(),
                                stats: stats_summary,
                            }
                        };
                        let _ = response_tx.send(summary);
                        tracing::info!("[dispatcher] recording stopped");
                    }
                    DispatcherCommand::UpdateConfigs { configs } => {
                        shared_configs = configs;
                        tracing::debug!(
                            "[dispatcher] updated configs: {} cameras",
                            shared_configs.len()
                        );
                    }
                    DispatcherCommand::Shutdown => {
                        // Clean up any in-progress recording
                        if recording_active.load(Ordering::SeqCst) {
                            recording_active.store(false, Ordering::SeqCst);
                            if let Some(handle) = recording_handle.take() {
                                handle.shutdown();
                            }
                        }
                        tracing::info!("[dispatcher] shutting down");
                        return;
                    }
                }
            }

            // ── Try to receive the next multiframe ──
            match multi_frame_receiver.try_recv() {
                Ok(mut payload) => {

                    // ── Deferred recorder creation (first multiframe after StartRecording) ──
                    if pending_recording.is_some() {
                        let params = pending_recording.take().unwrap();
                        match create_recorders(
                            &params,
                            &payload,
                            &shared_configs,
                        ) {
                            Ok((recorders, writers, session_dir, infos)) => {
                                let camera_count = payload.frames.len();
                                let dir_display = session_dir.display().to_string();
                                recording_stats = Some(RecordingStats::new(camera_count));
                                recording_handle = Some(spawn_recording_thread(
                                    recorders,
                                    writers,
                                    session_dir,
                                    infos,
                                ));
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

                    // ── Recording: send per-camera frames to recording thread ──
                    if recording_active.load(Ordering::SeqCst) {
                        let post_encode_ns =
                            crate::timestamps::performance::performance_counter_nanoseconds();

                        if let (Some(handle), Some(stats)) =
                            (recording_handle.as_ref(), recording_stats.as_mut())
                        {
                            let frames: Vec<RecordingFrameData> = payload
                                .frames
                                .iter()
                                .enumerate()
                                .map(|(i, frame)| RecordingFrameData {
                                    camera_index: i,
                                    jpeg_bytes: frame.data.as_bytes().to_vec(),
                                    frame_number: frame.frame_number,
                                    grab_timestamp_ns: frame.timestamps.frame_available_ns,
                                    timestamps: frame.timestamps.clone(),
                                })
                                .collect();
                            handle.send_frames(frames, post_encode_ns);
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
    shared_configs: &SharedConfigMap,
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

        // Look up the actual negotiated framerate from the shared camera config.
        // The camera thread writes the real FPS here after find_best_mjpg.
        // Fall back to 30.0 if the config hasn't been populated yet (shouldn't
        // happen — recording always starts after cameras are running).
        let target_fps = shared_configs
            .get(&identity.camera_id)
            .and_then(|cfg| {
                let guard = cfg.lock().ok()?;
                if guard.framerate > 0.0 {
                    Some(guard.framerate as f32)
                } else {
                    None
                }
            })
            .unwrap_or(30.0);

        let recorder = VideoRecorder::new(
            video_path,
            identity,
            frame.width,
            frame.height,
            target_fps,
            &VideoRecorderConfig::default(),
        )?;

        let csv_writer = CsvWriter::new(csv_path)?;

        recorders.push(recorder);
        writers.push(csv_writer);
        infos.push((identity.clone(), frame.width, frame.height));
    }

    Ok((recorders, writers, session_dir, infos))
}

use crate::camera::FrameData;
