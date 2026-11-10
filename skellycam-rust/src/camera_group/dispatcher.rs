//! Dispatcher thread — the single downstream consumer of `MultiFramePayload`.
//!
//! Spawned by `CameraGroup::start()`. Receives multiframes from the gatherer
//! via an unbounded channel and stores each camera's JPEG, unrotated, in the
//! latest-frames slot. Previews are built from that slot only when a consumer
//! asks for a newer frameset (`FrameSlots::frontend_payload`); recorders rotate
//! inside their own ffmpeg encode.
//!
//! When recording is active, per-camera JPEG frames are extracted and sent
//! via an unbounded channel to a dedicated recording thread — so the dispatcher
//! never blocks on ffmpeg pipe writes or CSV fsyncs.
//!
//! Spin-waits on the multiframe channel, the control channel, AND the recording
//! channel — never blocks, so config changes and recording commands stay responsive.

use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicI64, AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::camera::{CameraIdentity, FrameBytes, FrameLifecycleTimestamps, MultiFramePayload};
use crate::camera_group::recording_stats::RecordingStats;
use crate::recording::finalizer::RecordingSummary;
use crate::recording::{
    RecorderSpawnConfig, RecordingFrameData, RecordingHandle,
    VideoRecorderConfig, spawn_recording_thread,
};

use super::types::{DispatcherCommand, SharedConfigMap};

// ── Frontend payload type ─────────────────────────────────────────────────

/// Encoded frontend payload for one frameset, built on request by
/// `FrameSlots::frontend_payload`.
#[derive(Clone)]
pub struct FrontendPayload {
    pub frame_number: i64,
    pub timestamp_ns: f64,
    /// True camera capture rate computed from consecutive `frame_available_ns`
    /// timestamps with frame-skip correction. Independent of dispatcher load.
    pub camera_fps: f64,
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
    /// Rotation to apply for display and recording (SkellyCam / OpenCV rotation code,
    /// -1 = none); `jpeg_bytes` stays in sensor orientation.
    pub rotation: i32,
    pub jpeg_bytes: FrameBytes,
    /// Monotonic frame number — all cameras in the same multiframe share this.
    pub frame_number: i64,
    /// Per-frame lifecycle timestamps (loop_start, frame_available,
    /// post_jpeg_extract, pre_send, gatherer_received). All in nanoseconds
    /// since T=0 (process start).
    pub timestamps: FrameLifecycleTimestamps,
}

// ── Dispatcher spawn ────────────────────────────────────────────────────────

/// Spawn the dispatcher thread.
pub fn spawn_dispatcher(
    multi_frame_receiver: Receiver<MultiFramePayload>,
    control_receiver: Receiver<DispatcherCommand>,
    camera_fps: Arc<AtomicU64>,
    newest_frame_number: Arc<AtomicI64>,
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

        // Camera FPS tracking — computed from consecutive frame_available_ns timestamps
        let mut prev_camera_ts: Option<f64> = None;
        let mut prev_camera_fn: Option<i64> = None;
        let mut frame_intervals = FrameIntervals::default();

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
                        let result = match recording_handle.take() {
                            Some(handle) => handle.stop(stats_summary).map_err(|error| {
                                tracing::error!("[dispatcher] {error}");
                                error.to_string()
                            }),
                            None => {
                                tracing::warn!("[dispatcher] StopRecording but no recording handle");
                                Ok(RecordingSummary {
                                    total_frames_per_camera: 0,
                                    video_paths: Vec::new(),
                                    csv_paths: Vec::new(),
                                    recording_dir: PathBuf::new(),
                                    stats: stats_summary,
                                })
                            }
                        };
                        let _ = response_tx.send(result);
                        tracing::info!("[dispatcher] recording stopped");
                    }
                    DispatcherCommand::UpdateConfigs { configs } => {
                        shared_configs = configs;
                        // A new frame rate makes the measured intervals stale.
                        frame_intervals = FrameIntervals::default();
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

            // ── Wait for the next multiframe (wakes on arrival; commands are checked every 1 ms) ──
            match multi_frame_receiver.recv_timeout(Duration::from_millis(1)) {
                Ok(payload) => {
                    frame_intervals.push(&payload);

                    // ── Deferred recorder setup (first multiframe after StartRecording) ──
                    // Builds spawn configs (fast, no ffmpeg spawn) then enqueues
                    // a Setup command so the recording thread spawns ffmpeg on its
                    // own thread. Returns immediately — the dispatcher never blocks.
                    if pending_recording.is_some() {
                        let params = pending_recording.take().unwrap();
                        match build_recorder_configs(
                            &params,
                            &payload,
                            &shared_configs,
                            &frame_intervals,
                        ) {
                            Ok((recorder_configs, csv_paths, session_dir, infos)) => {
                                let camera_count = payload.frames.len();
                                let dir_display = session_dir.display().to_string();
                                recording_stats = Some(RecordingStats::new(camera_count));
                                recording_handle = Some(spawn_recording_thread(
                                    recorder_configs,
                                    csv_paths,
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
                                    "[dispatcher] failed to build recorder configs: {e}"
                                );
                                recording_active.store(false, Ordering::SeqCst);
                            }
                        }
                    }

                    // ── Each camera's bytes, shared (no copy) by raw_frames and recording ──
                    let jpeg_arcs: Vec<FrameBytes> = payload
                        .frames
                        .iter()
                        .map(|f| f.data.shared())
                        .collect();

                    // True camera capture rate from consecutive camera-side timestamps.
                    if !payload.frames.is_empty() {
                        let timestamp_ns = payload.frames.iter()
                            .map(|f| f.timestamps.frame_available_ns as f64)
                            .sum::<f64>() / payload.frames.len() as f64;
                        let frame_number = payload.frames[0].frame_number;
                        if let (Some(prev_ts), Some(prev_fn)) = (prev_camera_ts, prev_camera_fn) {
                            let delta_frames = frame_number - prev_fn;
                            if delta_frames > 0 && timestamp_ns > prev_ts {
                                let fps = 1_000_000_000.0 * delta_frames as f64 / (timestamp_ns - prev_ts);
                                camera_fps.store(fps.to_bits(), Ordering::Relaxed);
                            }
                        }
                        prev_camera_ts = Some(timestamp_ns);
                        prev_camera_fn = Some(frame_number);
                    }

                    // ── Store raw per-camera JPEGs for on-demand decode (Arc clone — no copy) ──
                    if let Ok(mut guard) = latest_raw_frames.lock() {
                        *guard = Some(
                            payload
                                .frames
                                .iter()
                                .zip(jpeg_arcs.iter())
                                .map(|(f, arc)| RawFrame {
                                    camera_id: f.identity.camera_id.clone(),
                                    camera_index: f.identity.camera_index,
                                    width: f.width,
                                    height: f.height,
                                    rotation: f.rotation,
                                    jpeg_bytes: Arc::clone(arc),
                                    frame_number: f.frame_number,
                                    timestamps: f.timestamps.clone(),
                                })
                                .collect(),
                        );
                        if let Some(first) = payload.frames.first() {
                            newest_frame_number.store(first.frame_number, Ordering::Release);
                        }
                    }

                    // ── Recording: send per-camera frames to recording thread (Arc clone — no copy) ──
                    if recording_active.load(Ordering::SeqCst) {
                        let post_encode_ns =
                            crate::timestamps::performance::performance_counter_nanoseconds();

                        if let (Some(handle), Some(stats)) =
                            (recording_handle.as_ref(), recording_stats.as_mut())
                        {
                            let frames: Vec<RecordingFrameData> = payload
                                .frames
                                .iter()
                                .zip(jpeg_arcs.iter())
                                .enumerate()
                                .map(|(i, (frame, arc))| RecordingFrameData {
                                    camera_index: i,
                                    jpeg_bytes: Arc::clone(arc),
                                    frame_number: frame.frame_number,
                                    grab_timestamp_ns: frame.timestamps.frame_available_ns,
                                    timestamps: frame.timestamps.clone(),
                                })
                                .collect();
                            handle.send_frames(frames, post_encode_ns);
                            stats.push_multiframe(&payload, post_encode_ns);
                            if let Some(reason) = handle.failure() {
                                // A writer failed: end the recording now; stopping it reports why.
                                tracing::error!("[dispatcher] recording ended: {reason}");
                                recording_active.store(false, Ordering::SeqCst);
                            }
                        }
                    }
                }
                Err(mpsc::RecvTimeoutError::Timeout) => {}
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    tracing::warn!("[dispatcher] gatherer disconnected, exiting");
                    break;
                }
            }
        }
    })
    .expect("Failed to spawn dispatcher thread")
}

// ── Measured frame rate ─────────────────────────────────────────────────────

/// Each camera's most recent frame intervals, read to read (consecutive `frame_available_ns`), by position in
/// the frameset. A recording's videos carry their median rate, as the OpenCV backend's recorder does with its
/// last 1000 read-to-read intervals.
#[derive(Default)]
struct FrameIntervals {
    previous: Vec<Option<(i64, i64)>>,
    intervals: Vec<VecDeque<i64>>,
}

impl FrameIntervals {
    const WINDOW: usize = 1000;

    fn push(&mut self, payload: &MultiFramePayload) {
        if self.previous.len() != payload.frames.len() {
            *self = Self { previous: vec![None; payload.frames.len()], intervals: vec![VecDeque::new(); payload.frames.len()] };
        }
        for (position, frame) in payload.frames.iter().enumerate() {
            let now = (frame.frame_number, frame.timestamps.frame_available_ns);
            if let Some((number, time)) = self.previous[position].replace(now) {
                if now.0 == number + 1 && now.1 > time {
                    let intervals = &mut self.intervals[position];
                    if intervals.len() == Self::WINDOW {
                        intervals.pop_front();
                    }
                    intervals.push_back(now.1 - time);
                }
            }
        }
    }

    /// The median measured rate of the camera at `position`, if any interval was measured.
    fn median_fps(&self, position: usize) -> Option<f32> {
        let mut intervals: Vec<i64> = self.intervals.get(position)?.iter().copied().collect();
        if intervals.is_empty() {
            return None;
        }
        intervals.sort_unstable();
        Some((1e9 / intervals[intervals.len() / 2] as f64) as f32)
    }
}

// ── Recording lifecycle helpers ────────────────────────────────────────────

/// Build per-camera recorder spawn configs from the first multiframe.
///
/// Purely computational — computes paths and parameters, no I/O.
/// Directory creation happens in the recording thread's Setup handler so it
/// never blocks the dispatcher hot loop.
fn build_recorder_configs(
    params: &super::types::RecordingParams,
    payload: &MultiFramePayload,
    shared_configs: &SharedConfigMap,
    frame_intervals: &FrameIntervals,
) -> anyhow::Result<(
    Vec<RecorderSpawnConfig>,
    Vec<PathBuf>,
    PathBuf,
    Vec<(CameraIdentity, u32, u32)>,
)> {
    let session_name = params.label.clone().unwrap_or_else(|| {
        let now = chrono::Local::now();
        let gmt_offset = now.offset().local_minus_utc() / 3600;
        let base = now.format("%Y-%m-%dT%H_%M_%S").to_string();
        let tag = params.label.as_deref().unwrap_or("recording");
        format!("{base}_gmt{gmt_offset:+}_{tag}")
    });
    let output_dir = PathBuf::from(&params.output_dir);
    let session_dir = output_dir.join(&session_name);
    let videos_dir = session_dir.join("synchronized_videos");
    let timestamps_dir = videos_dir.join("timestamps").join("camera_timestamps");

    let mut recorder_configs = Vec::with_capacity(payload.frames.len());
    let mut csv_paths = Vec::with_capacity(payload.frames.len());
    let mut infos: Vec<(CameraIdentity, u32, u32)> =
        Vec::with_capacity(payload.frames.len());

    for (position, frame) in payload.frames.iter().enumerate() {
        let identity = &frame.identity;
        let video_path = videos_dir.join(format!("{session_name}.id-{}.idx-{}.mp4", identity.camera_id, identity.camera_index));
        let csv_path = timestamps_dir.join(format!("{session_name}.camera{}.timestamps.csv", identity.camera_id));

        // The video carries the frame rate measured from this camera's frames (median interval), as the
        // OpenCV backend's videos do; the negotiated rate only when no interval has been measured yet.
        let target_fps = match frame_intervals.median_fps(position) {
            Some(measured) => measured,
            None => shared_configs
                .get(&identity.camera_id)
                .and_then(|cfg| cfg.lock().ok().map(|guard| guard.framerate as f32))
                .filter(|negotiated| *negotiated > 0.0)
                .ok_or_else(|| anyhow::anyhow!("Camera {}: no measured or negotiated frame rate", identity.camera_id))?,
        };

        // ffmpeg receives the camera's JPEGs in sensor orientation and rotates while encoding,
        // so the video file has the rotated size.
        recorder_configs.push(RecorderSpawnConfig {
            output_path: video_path,
            identity: (**identity).clone(),
            width: frame.width,
            height: frame.height,
            rotation: frame.rotation,
            target_fps,
            config: VideoRecorderConfig::default(),
        });

        csv_paths.push(csv_path);
        let (video_width, video_height) =
            crate::camera_group::preview::rotated_size(frame.width, frame.height, frame.rotation);
        infos.push(((**identity).clone(), video_width, video_height));
    }

    Ok((recorder_configs, csv_paths, session_dir, infos))
}


#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use super::*;
    use crate::camera::{FrameData, FramePacket, GathererTimestamps};

    fn frameset(frame_number: i64, available_ns: &[i64]) -> MultiFramePayload {
        MultiFramePayload {
            frames: available_ns.iter().enumerate().map(|(index, &frame_available_ns)| FramePacket {
                data: FrameData::Mjpg(Arc::new(Vec::new())),
                width: 64,
                height: 48,
                rotation: -1,
                timestamps: FrameLifecycleTimestamps { frame_available_ns, ..FrameLifecycleTimestamps::new() },
                identity: Arc::new(CameraIdentity {
                    camera_name: "Test Cam".into(),
                    camera_index: index as i32,
                    camera_id: format!("cam{index}"),
                    device_path: String::new(),
                    formats: Vec::new(),
                }),
                frame_number,
            }).collect(),
            frame_number,
            gatherer_timestamps: GathererTimestamps::new(),
        }
    }

    #[test]
    fn the_video_rate_is_the_median_measured_interval() {
        // These cameras at "60 fps": 16 ms apart, with a 33 ms gap every 24th frame (2026-11-10 recording).
        let mut intervals = FrameIntervals::default();
        let mut time = 0;
        for number in 0..200 {
            time += if number % 24 == 23 { 33_000_000 } else { 16_000_000 };
            intervals.push(&frameset(number, &[time, time + 1_000]));
        }
        assert_eq!(intervals.median_fps(0), Some(62.5));
        assert_eq!(intervals.median_fps(1), Some(62.5));
    }

    #[test]
    fn skipped_frame_numbers_and_a_new_camera_count_restart_the_measurement() {
        let mut intervals = FrameIntervals::default();
        intervals.push(&frameset(0, &[0]));
        intervals.push(&frameset(5, &[100_000_000])); // not consecutive: no interval
        assert_eq!(intervals.median_fps(0), None);
        intervals.push(&frameset(6, &[120_000_000]));
        assert_eq!(intervals.median_fps(0), Some(50.0));
        intervals.push(&frameset(7, &[140_000_000, 140_000_000])); // two cameras now
        assert_eq!(intervals.median_fps(0), None);
    }
}
