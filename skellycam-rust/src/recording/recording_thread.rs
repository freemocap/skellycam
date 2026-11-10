//! Recording writers: one thread per camera, each owning that camera's `VideoRecorder` (ffmpeg) and timestamp
//! `CsvWriter`, so one slow or failed ffmpeg cannot stall the other cameras.
//!
//! The dispatcher hands each camera's frame to that camera's writer through an unbounded queue (frames are never
//! dropped) and never blocks. Each writer sets itself up (directories, ffmpeg, timestamp file) on its own thread,
//! then writes its frames in order. A writer that fails records why and stops; the dispatcher sees the failure on
//! its next frameset and ends the recording, and `stop()` returns the reason.
//!
//! ```text
//! dispatcher                              writer thread per camera
//! spawn_recording_thread() ──────────→    create dirs, spawn ffmpeg, create CSV
//! send_frames(frames, ts)  ── queue i ──→ feed_frame() + write_row()
//! failure()                ←── first error, if any
//! stop(stats)              ── close ───→  drain queue, finish ffmpeg + CSV → paths; then finalize
//! ```

use std::path::PathBuf;
use std::sync::atomic::{AtomicI64, AtomicUsize, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread::{self, JoinHandle};

use crate::camera::{CameraIdentity, FrameLifecycleTimestamps};
use crate::camera_group::recording_stats::RecordingStatsSummary;
use crate::recording::finalizer::{self, RecordingSummary};
use crate::recording::{RecorderSpawnConfig, VideoRecorder};
use crate::timestamps::performance::performance_counter_nanoseconds;
use crate::timestamps::CsvWriter;

// ── Frame data ─────────────────────────────────────────────────────────────

/// One camera's frame, sent from the dispatcher to that camera's writer.
pub struct RecordingFrameData {
    pub camera_index: usize,
    pub jpeg_bytes: crate::camera::FrameBytes,
    pub frame_number: i64,
    /// `frame_available_ns` from the camera thread — the grab timestamp.
    pub grab_timestamp_ns: i64,
    /// Full lifecycle timestamps for the CSV row.
    pub timestamps: FrameLifecycleTimestamps,
}

struct Queued {
    frame: RecordingFrameData,
    recorded_timestamp_ns: i64,
    enqueued_ns: i64,
}

/// How far one camera's writer fell behind during the recording.
#[derive(Debug, Clone, Default)]
pub struct WriterBacklog {
    pub camera_id: String,
    /// Most frames waiting in this camera's queue at once.
    pub max_queued_frames: usize,
    /// Longest a frame waited in the queue before its writer took it.
    pub max_wait_ns: i64,
}

type WriterResult = Result<(PathBuf, PathBuf), String>;

struct CameraWriter {
    camera_id: String,
    sender: Option<mpsc::Sender<Queued>>,
    queued: Arc<AtomicUsize>,
    max_queued: Arc<AtomicUsize>,
    max_wait_ns: Arc<AtomicI64>,
    thread: Option<JoinHandle<WriterResult>>,
}

// ── Handle ─────────────────────────────────────────────────────────────────

/// The writers of one recording. Held by the dispatcher; `send_frames()` never blocks.
pub struct RecordingHandle {
    writers: Vec<CameraWriter>,
    failure: Arc<Mutex<Option<String>>>,
    recording_dir: PathBuf,
    camera_infos: Vec<(CameraIdentity, u32, u32)>,
}

impl RecordingHandle {
    /// Queue each camera's frame for that camera's writer.
    pub fn send_frames(&self, frames: Vec<RecordingFrameData>, recorded_timestamp_ns: i64) {
        let enqueued_ns = performance_counter_nanoseconds();
        for frame in frames {
            let Some(writer) = self.writers.get(frame.camera_index) else { continue };
            let Some(sender) = &writer.sender else { continue };
            let depth = writer.queued.fetch_add(1, Ordering::SeqCst) + 1;
            writer.max_queued.fetch_max(depth, Ordering::Relaxed);
            if sender.send(Queued { frame, recorded_timestamp_ns, enqueued_ns }).is_err() {
                writer.queued.fetch_sub(1, Ordering::SeqCst); // the writer stopped; its failure says why
            }
        }
    }

    /// Why the recording failed, if a writer failed: the first error, with its camera.
    pub fn failure(&self) -> Option<String> {
        self.failure.lock().ok().and_then(|failure| failure.clone())
    }

    /// Each writer's backlog so far.
    pub fn backlog(&self) -> Vec<WriterBacklog> {
        self.writers.iter()
            .map(|writer| WriterBacklog {
                camera_id: writer.camera_id.clone(),
                max_queued_frames: writer.max_queued.load(Ordering::Relaxed),
                max_wait_ns: writer.max_wait_ns.load(Ordering::Relaxed),
            })
            .collect()
    }

    /// Write every queued frame, finish every file, and finalize the recording; a failure is the error.
    pub fn stop(mut self, stats: Option<RecordingStatsSummary>) -> anyhow::Result<RecordingSummary> {
        let results = self.finish_writers();
        for backlog in self.backlog() {
            tracing::info!(
                "[recording] camera {}: at most {} frames queued, longest wait {:.1} ms",
                backlog.camera_id, backlog.max_queued_frames, backlog.max_wait_ns as f64 / 1e6,
            );
        }
        if let Some(reason) = self.failure() {
            anyhow::bail!("Recording failed: {reason}");
        }
        let mut video_paths = Vec::with_capacity(results.len());
        let mut csv_paths = Vec::with_capacity(results.len());
        for result in results {
            let (video, csv) = result.map_err(|reason| anyhow::anyhow!("Recording failed: {reason}"))?;
            video_paths.push(video);
            csv_paths.push(csv);
        }
        finalizer::finalize_recording(&self.recording_dir, &self.camera_infos, &video_paths, &csv_paths, stats)
    }

    /// End the recording without a summary (shutdown): writers still finish their files.
    pub fn shutdown(mut self) {
        let _ = self.finish_writers();
    }

    /// Close every queue, then wait for each writer to drain it and finish its files.
    fn finish_writers(&mut self) -> Vec<WriterResult> {
        for writer in &mut self.writers {
            writer.sender.take();
        }
        self.writers.iter_mut()
            .map(|writer| match writer.thread.take().map(JoinHandle::join) {
                Some(Ok(result)) => result,
                Some(Err(_)) => Err(format!("camera {}: writer thread panicked", writer.camera_id)),
                None => Err(format!("camera {}: writer already finished", writer.camera_id)),
            })
            .collect()
    }
}

// ── Spawn ──────────────────────────────────────────────────────────────────

/// Start one writer per camera (each spawns its own ffmpeg) and return at once.
pub fn spawn_recording_thread(
    recorder_configs: Vec<RecorderSpawnConfig>,
    writer_paths: Vec<PathBuf>,
    recording_dir: PathBuf,
    camera_infos: Vec<(CameraIdentity, u32, u32)>,
) -> RecordingHandle {
    let failure = Arc::new(Mutex::new(None));
    let writers = recorder_configs.into_iter()
        .zip(writer_paths)
        .map(|(config, csv_path)| spawn_camera_writer(config, csv_path, Arc::clone(&failure)))
        .collect();
    RecordingHandle { writers, failure, recording_dir, camera_infos }
}

fn spawn_camera_writer(config: RecorderSpawnConfig, csv_path: PathBuf, failure: Arc<Mutex<Option<String>>>) -> CameraWriter {
    let (sender, receiver) = mpsc::channel::<Queued>();
    let camera_id = config.identity.camera_id.clone();
    let (queued, max_queued, max_wait_ns) =
        (Arc::new(AtomicUsize::new(0)), Arc::new(AtomicUsize::new(0)), Arc::new(AtomicI64::new(0)));
    let thread = {
        let (queued, max_wait_ns, label) = (Arc::clone(&queued), Arc::clone(&max_wait_ns), config.identity.label());
        thread::Builder::new()
            .name(format!("recording-{camera_id}"))
            .spawn(move || {
                let result = write_camera(config, csv_path, receiver, &queued, &max_wait_ns);
                if let Err(reason) = &result {
                    tracing::error!("[recording] camera {label}: {reason}");
                    if let Ok(mut first) = failure.lock() {
                        first.get_or_insert_with(|| format!("camera {label}: {reason}"));
                    }
                }
                result
            })
            .expect("Failed to spawn recording writer thread")
    };
    CameraWriter { camera_id, sender: Some(sender), queued, max_queued, max_wait_ns, thread: Some(thread) }
}

/// One camera's writer: set up, write every queued frame in order, finish both files.
fn write_camera(
    config: RecorderSpawnConfig,
    csv_path: PathBuf,
    receiver: mpsc::Receiver<Queued>,
    queued: &AtomicUsize,
    max_wait_ns: &AtomicI64,
) -> WriterResult {
    for directory in [config.output_path.parent(), csv_path.parent()].into_iter().flatten() {
        std::fs::create_dir_all(directory)
            .map_err(|error| format!("could not create {}: {error}", directory.display()))?;
    }
    let mut recorder = VideoRecorder::spawn(config).map_err(|error| format!("could not start ffmpeg: {error}"))?;
    let mut writer = CsvWriter::new(csv_path).map_err(|error| format!("could not create the timestamp file: {error}"))?;
    while let Ok(item) = receiver.recv() {
        let pre_record_ns = performance_counter_nanoseconds();
        max_wait_ns.fetch_max(pre_record_ns - item.enqueued_ns, Ordering::Relaxed);
        let frame = &item.frame;
        recorder.feed_frame(&frame.jpeg_bytes, frame.frame_number, frame.grab_timestamp_ns, item.recorded_timestamp_ns)
            .map_err(|error| format!("video write failed at frame {}: {error}", frame.frame_number))?;
        writer.write_row(frame.frame_number, &frame.timestamps, pre_record_ns, performance_counter_nanoseconds())
            .map_err(|error| format!("timestamp write failed at frame {}: {error}", frame.frame_number))?;
        queued.fetch_sub(1, Ordering::SeqCst);
    }
    let video = recorder.output_path().to_path_buf();
    recorder.finish().map_err(|error| format!("ffmpeg did not finish the video: {error}"))?;
    let csv = writer.finish().map_err(|error| format!("could not finish the timestamp file: {error}"))?;
    Ok((video, csv))
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use super::*;
    use crate::recording::VideoRecorderConfig;

    fn identity(camera_id: &str) -> CameraIdentity {
        CameraIdentity {
            camera_name: "Test Cam".into(),
            camera_index: 0,
            camera_id: camera_id.into(),
            device_path: String::new(),
            formats: Vec::new(),
        }
    }

    #[test]
    fn a_writer_that_cannot_start_fails_the_recording_with_its_reason() {
        let root = std::env::temp_dir().join(format!("skellycam-writer-test-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let blocker = root.join("blocker"); // a file where the video folder should be
        std::fs::write(&blocker, b"").unwrap();
        let config = RecorderSpawnConfig {
            output_path: blocker.join("videos").join("cam0.mp4"),
            identity: identity("cam0"),
            width: 64,
            height: 48,
            rotation: -1,
            target_fps: 30.0,
            config: VideoRecorderConfig::default(),
        };
        let handle = spawn_recording_thread(vec![config], vec![root.join("cam0.csv")], root.clone(),
                                            vec![(identity("cam0"), 64, 48)]);
        handle.send_frames(vec![RecordingFrameData {
            camera_index: 0,
            jpeg_bytes: Arc::new(vec![0u8; 16]),
            frame_number: 0,
            grab_timestamp_ns: 0,
            timestamps: FrameLifecycleTimestamps::new(),
        }], 0);
        let error = match handle.stop(None) {
            Ok(_) => panic!("a writer that cannot start must fail the recording"),
            Err(error) => error.to_string(),
        };
        assert!(error.contains("Recording failed: camera") && error.contains("could not create"), "{error}");
        let _ = std::fs::remove_dir_all(&root);
    }
}
