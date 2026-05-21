//! Recording thread — owns `VideoRecorder`s and `CsvWriter`s, performing all
//! recording I/O off the dispatcher's critical path.
//!
//! Spawned by the dispatcher after building recorder configs. Receives
//! per-camera frame data via an unbounded `mpsc::channel()`, so the dispatcher
//! never blocks on ffmpeg pipe writes or CSV fsyncs.
//!
//! ## Lifecycle
//!
//! ```text
//! dispatcher                         recording_thread
//! ─────────                          ────────────────
//! build_recorder_configs()
//! spawn_recording_thread() ───→      [Setup enqueued, thread spawned]
//!                                     recv() → Setup → spawn ffmpeg + create CSV writers
//!                                     (FeedFrames silently queue in the channel)
//! recording_active = true
//! send_frames(frames, ts)  ───→      feed_frame() + write_row() per camera
//! send_frames(frames, ts)  ───→      feed_frame() + write_row() per camera
//!   ...                                 ...
//! handle.stop(stats)        ───→      finalize_all() → summary via oneshot → exit
//! ```

use std::path::PathBuf;
use std::sync::mpsc;
use std::thread::{self, JoinHandle};

use crate::camera::{CameraIdentity, FrameLifecycleTimestamps};
use crate::camera_group::recording_stats::RecordingStatsSummary;
use crate::recording::finalizer::{self, RecordingSummary};
use crate::recording::{RecorderSpawnConfig, VideoRecorder};
use crate::timestamps::CsvWriter;

// ── Frame data ─────────────────────────────────────────────────────────────

/// Per-camera frame data sent from the dispatcher to the recording thread.
///
/// Carries everything the recording thread needs to write one frame to ffmpeg
/// and one row to the timestamp CSV — without holding a reference to the
/// `MultiFramePayload`.
pub struct RecordingFrameData {
    pub camera_index: usize,
    pub jpeg_bytes: Vec<u8>,
    pub frame_number: i64,
    /// `frame_available_ns` from the camera thread — the grab timestamp.
    pub grab_timestamp_ns: i64,
    /// Full lifecycle timestamps for the CSV row.
    pub timestamps: FrameLifecycleTimestamps,
}

// ── Commands ───────────────────────────────────────────────────────────────

enum RecordingCommand {
    /// Initialize recorders by spawning ffmpeg subprocesses and creating CSV
    /// writers. Always the first command sent to the recording thread.
    /// Processing blocks the recording thread while ffmpeg spawns — the work
    /// we moved off the dispatcher. FeedFrames arriving during this time
    /// silently queue in the unbounded channel.
    Setup {
        recorder_configs: Vec<RecorderSpawnConfig>,
        writer_paths: Vec<PathBuf>,
        recording_dir: PathBuf,
        camera_infos: Vec<(CameraIdentity, u32, u32)>,
    },
    /// Feed one multiframe's worth of per-camera frames.
    FeedFrames {
        frames: Vec<RecordingFrameData>,
        recorded_timestamp_ns: i64,
    },
    /// Stop recording, finalize all files, and return the summary.
    Stop {
        response_tx: mpsc::Sender<RecordingSummary>,
        stats: Option<RecordingStatsSummary>,
    },
    /// Emergency shutdown — finalize and exit, discarding the summary.
    Shutdown,
}

// ── Handle ─────────────────────────────────────────────────────────────────

/// Handle to the recording thread.
///
/// Held by the dispatcher. `send_frames()` is non-blocking (unbounded channel).
/// `stop()` and `shutdown()` consume the handle and join the thread.
pub struct RecordingHandle {
    sender: mpsc::Sender<RecordingCommand>,
    thread: Option<JoinHandle<()>>,
}

impl RecordingHandle {
    /// Send one multiframe's per-camera frames to the recording thread.
    ///
    /// Non-blocking: uses an unbounded channel. If the recording thread has
    /// died (panic), the send error is silently ignored — the dispatcher
    /// detects the dead thread on the next `stop()` or `shutdown()`.
    pub fn send_frames(&self, frames: Vec<RecordingFrameData>, recorded_timestamp_ns: i64) {
        let _ = self.sender.send(RecordingCommand::FeedFrames {
            frames,
            recorded_timestamp_ns,
        });
    }

    /// Stop recording and wait for finalization.
    ///
    /// Sends a `Stop` command to the recording thread, then blocks on the
    /// oneshot response channel until finalization completes. Joins the
    /// recording thread before returning.
    pub fn stop(mut self, stats: Option<RecordingStatsSummary>) -> anyhow::Result<RecordingSummary> {
        let (tx, rx) = mpsc::channel();
        let _ = self.sender.send(RecordingCommand::Stop {
            response_tx: tx,
            stats,
        });
        match rx.recv() {
            Ok(summary) => {
                if let Some(thread) = self.thread.take() {
                    let _ = thread.join();
                }
                Ok(summary)
            }
            Err(_) => {
                if let Some(thread) = self.thread.take() {
                    let _ = thread.join();
                }
                anyhow::bail!("Recording thread disconnected before sending summary")
            }
        }
    }

    /// Emergency shutdown — tells the recording thread to finalize and exit.
    ///
    /// Does not wait for a summary. Joins the thread.
    pub fn shutdown(mut self) {
        let _ = self.sender.send(RecordingCommand::Shutdown);
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

// ── Spawn ──────────────────────────────────────────────────────────────────

/// Spawn the recording thread.
///
/// Enqueues a `Setup` command carrying recorder spawn configs and CSV writer
/// paths, then spawns the worker thread. The recording thread will spawn
/// ffmpeg processes on its own thread — this call returns immediately.
///
/// The dispatcher calls this after `build_recorder_configs()`.
pub fn spawn_recording_thread(
    recorder_configs: Vec<RecorderSpawnConfig>,
    writer_paths: Vec<PathBuf>,
    recording_dir: PathBuf,
    camera_infos: Vec<(CameraIdentity, u32, u32)>,
) -> RecordingHandle {
    let (tx, rx) = mpsc::channel::<RecordingCommand>();

    // Enqueue Setup as the first command. Sent before the thread starts,
    // so the recording thread's first recv() is guaranteed to be Setup,
    // followed by any FeedFrames the dispatcher sends after setting
    // recording_active = true.
    let _ = tx.send(RecordingCommand::Setup {
        recorder_configs,
        writer_paths,
        recording_dir,
        camera_infos,
    });

    let thread = thread::Builder::new()
        .name("recording_thread".into())
        .spawn(move || {
            run(rx);
        })
        .expect("Failed to spawn recording thread");

    RecordingHandle {
        sender: tx,
        thread: Some(thread),
    }
}

// ── Main loop ──────────────────────────────────────────────────────────────

fn run(receiver: mpsc::Receiver<RecordingCommand>) {
    // Recorders and writers are created lazily from the Setup command.
    // Before Setup completes, FeedFrames accumulate in the channel buffer.
    let mut recorders: Option<Vec<VideoRecorder>> = None;
    let mut writers: Option<Vec<CsvWriter>> = None;
    let mut recording_dir: Option<PathBuf> = None;
    let mut camera_infos: Option<Vec<(CameraIdentity, u32, u32)>> = None;

    loop {
        match receiver.recv() {
            Ok(RecordingCommand::Setup {
                recorder_configs,
                writer_paths,
                recording_dir: dir,
                camera_infos: infos,
            }) => {
                tracing::info!(
                    "[recording_thread] Setup: spawning {} recorder(s)...",
                    recorder_configs.len()
                );

                // ── Spawn all ffmpeg processes (THE work moved off the dispatcher) ──
                let mut recs = Vec::with_capacity(recorder_configs.len());
                for cfg in recorder_configs {
                    match VideoRecorder::spawn(cfg) {
                        Ok(r) => recs.push(r),
                        Err(e) => {
                            tracing::error!(
                                "[recording_thread] failed to spawn recorder: {e}"
                            );
                            for r in recs {
                                drop(r);
                            }
                            return;
                        }
                    }
                }

                // ── Create CSV writers ──
                let mut wrs = Vec::with_capacity(writer_paths.len());
                for path in writer_paths {
                    match CsvWriter::new(path) {
                        Ok(w) => wrs.push(w),
                        Err(e) => {
                            tracing::error!(
                                "[recording_thread] failed to create CSV writer: {e}"
                            );
                            for r in recs {
                                drop(r);
                            }
                            for w in wrs {
                                drop(w);
                            }
                            return;
                        }
                    }
                }

                recorders = Some(recs);
                writers = Some(wrs);
                recording_dir = Some(dir);
                camera_infos = Some(infos);

                tracing::info!(
                    "[recording_thread] Setup complete — ready to receive frames"
                );
            }

            Ok(RecordingCommand::FeedFrames {
                frames,
                recorded_timestamp_ns,
            }) => {
                if let (Some(recs), Some(wrs)) = (&mut recorders, &mut writers) {
                    for frame_data in &frames {
                        let i = frame_data.camera_index;
                        if let (Some(recorder), Some(writer)) =
                            (recs.get_mut(i), wrs.get_mut(i))
                        {
                            if let Err(e) = recorder.feed_frame(
                                &frame_data.jpeg_bytes,
                                frame_data.frame_number,
                                frame_data.grab_timestamp_ns,
                                recorded_timestamp_ns,
                            ) {
                                tracing::error!(
                                    "[recording_thread] recorder error camera {i}: {e}"
                                );
                            }
                            if let Err(e) = writer.write_row(
                                frame_data.frame_number,
                                &frame_data.timestamps,
                            ) {
                                tracing::error!(
                                    "[recording_thread] CSV write error camera {i}: {e}"
                                );
                            }
                        }
                    }
                }
            }

            Ok(RecordingCommand::Stop { response_tx, stats }) => {
                let recs = recorders.take().unwrap_or_default();
                let wrs = writers.take().unwrap_or_default();
                let dir = recording_dir.take().unwrap_or_default();
                let infos = camera_infos.take().unwrap_or_default();
                let summary = finalize_all(recs, wrs, &dir, &infos, stats);
                let _ = response_tx.send(summary);
                return;
            }

            Ok(RecordingCommand::Shutdown) => {
                let recs = recorders.take().unwrap_or_default();
                let wrs = writers.take().unwrap_or_default();
                let dir = recording_dir.take().unwrap_or_default();
                let infos = camera_infos.take().unwrap_or_default();
                let _ = finalize_all(recs, wrs, &dir, &infos, None);
                return;
            }

            Err(_) => {
                tracing::warn!(
                    "[recording_thread] channel disconnected without Stop/Shutdown"
                );
                return;
            }
        }
    }
}

// ── Finalization ───────────────────────────────────────────────────────────

/// Finalize all recorders and writers, then write `recording_info.json`.
fn finalize_all(
    recorders: Vec<VideoRecorder>,
    writers: Vec<CsvWriter>,
    recording_dir: &PathBuf,
    camera_infos: &[(CameraIdentity, u32, u32)],
    stats: Option<RecordingStatsSummary>,
) -> RecordingSummary {
    let camera_count = recorders.len();
    let mut video_paths = Vec::with_capacity(camera_count);
    let mut csv_paths = Vec::with_capacity(camera_count);

    for recorder in recorders {
        let frame_count = recorder.frame_count();
        let path = recorder.output_path().to_path_buf();
        match recorder.finish() {
            Ok(timestamps) => {
                video_paths.push(path);
                tracing::info!(
                    "[recording_thread] recorder finished: {frame_count} frames, {} timestamps",
                    timestamps.len()
                );
            }
            Err(e) => {
                tracing::error!("[recording_thread] recorder finish error: {e}");
            }
        }
    }

    for writer in writers {
        match writer.finish() {
            Ok(path) => csv_paths.push(path),
            Err(e) => tracing::error!("[recording_thread] CSV finish error: {e}"),
        }
    }

    if camera_infos.len() != video_paths.len() || camera_infos.len() != csv_paths.len() {
        tracing::error!(
            "[recording_thread] mismatch: {} camera infos, {} videos, {} CSVs — skipping recording_info.json",
            camera_infos.len(),
            video_paths.len(),
            csv_paths.len(),
        );
        return RecordingSummary {
            total_frames_per_camera: 0,
            video_paths,
            csv_paths,
            info_json_path: PathBuf::new(),
            stats,
        };
    }

    let total = video_paths.len() as u64;
    match finalizer::finalize_recording(recording_dir, camera_infos, &video_paths, &csv_paths, stats)
    {
        Ok(summary) => {
            tracing::info!(
                "[recording_thread] recording_info.json written → {}",
                summary.info_json_path.display(),
            );
            summary
        }
        Err(e) => {
            tracing::error!("[recording_thread] finalize_recording error: {e}");
            RecordingSummary {
                total_frames_per_camera: total,
                video_paths,
                csv_paths,
                info_json_path: PathBuf::new(),
                stats: None,
            }
        }
    }
}
