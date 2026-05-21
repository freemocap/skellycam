//! Per-camera video recorder: ffmpeg subprocess fed MJPEG frames via stdin.
//!
//! Each VideoRecorder spawns an ffmpeg child process that reads MJPEG frames
//! from `pipe:0`, decodes them, and re-encodes to H.264. Frames are fed via
//! `feed_frame()`. `finish()` closes stdin (EOF to ffmpeg) and returns
//! per-frame timestamps.

use std::io::Write;
use std::path::PathBuf;
use std::process::ChildStdin;

use anyhow::Context;
use ffmpeg_sidecar::command::FfmpegCommand;

use crate::camera::CameraIdentity;

/// Parameters controlling ffmpeg encode settings.
///
/// All fields have sensible defaults. In the future these will be
/// user-configurable via the frontend.
#[derive(Debug, Clone)]
pub struct VideoRecorderConfig {
    /// ffmpeg input format (`-f`). "image2pipe" means one image per write.
    pub input_format: String,
    /// Input codec (`-c:v` on the input side). "mjpeg" for MJPEG frames.
    pub input_codec: String,
    /// Output codec (`-c:v` on the output side).
    pub output_codec: String,
    /// libx264 preset: "ultrafast", "medium", "veryslow", etc.
    pub preset: String,
    /// Constant Rate Factor (0-51). 18 = visually lossless, 23 = default.
    pub crf: u32,
    /// Output pixel format. "yuv420p" for maximum compatibility.
    pub pix_fmt: String,
}

impl Default for VideoRecorderConfig {
    fn default() -> Self {
        Self {
            input_format: "image2pipe".into(),
            input_codec: "mjpeg".into(),
            output_codec: "libx264".into(),
            preset: "medium".into(),
            crf: 18,
            pix_fmt: "yuv420p".into(),
        }
    }
}

/// Pure-data config bundle for deferred `VideoRecorder` creation.
///
/// Contains everything `VideoRecorder::new()` needs without performing any
/// I/O or process spawn. Constructed on the dispatcher thread (fast) and
/// consumed by the recording thread's Setup handler (where ffmpeg spawns).
#[derive(Debug, Clone)]
pub struct RecorderSpawnConfig {
    pub output_path: PathBuf,
    pub identity: CameraIdentity,
    pub width: u32,
    pub height: u32,
    pub target_fps: f32,
    pub config: VideoRecorderConfig,
}

/// Timestamp record for a single frame written to video.
///
/// This maps to one row in the per-camera timestamp CSV and provides
/// the join key (`frame_number`) for cross-camera DataFrames.
#[derive(Debug, Clone)]
pub struct FrameTimestamp {
    pub frame_number: i64,
    /// Monotonic nanosecond timestamp from `performance_counter_nanoseconds()`,
    /// captured inside the camera thread immediately before `Cap_captureFrame`.
    pub grab_timestamp_ns: i64,
    /// Timestamp of when this frame was written to the ffmpeg pipe.
    /// Serves as a recording-side timestamp for latency analysis.
    pub recorded_timestamp_ns: i64,
}

/// Manages an ffmpeg subprocess that encodes MJPEG frames to H.264 video.
///
/// On construction, spawns `ffmpeg` reading MJPEG from `pipe:0`.
/// Call `feed_frame()` for each frame. Call `finish()` to finalize the
/// video and return all timestamps.
///
/// If `VideoRecorder` is dropped without calling `finish()`, the ffmpeg
/// process is killed and the partial video file is left on disk.
pub struct VideoRecorder {
    ffmpeg_child: ffmpeg_sidecar::child::FfmpegChild,
    stdin: Option<ChildStdin>,
    output_path: PathBuf,
    frame_count: u64,
    timestamps: Vec<FrameTimestamp>,
}

impl VideoRecorder {
    /// Spawn a new ffmpeg subprocess recording to `output_path`.
    ///
    /// `width` and `height` are rounded down to even numbers (required by
    /// H.264 yuv420p chroma subsampling).
    pub fn new(
        output_path: PathBuf,
        identity: &CameraIdentity,
        width: u32,
        height: u32,
        target_fps: f32,
        config: &VideoRecorderConfig,
    ) -> anyhow::Result<Self> {
        let even_width = width & !1;
        let even_height = height & !1;
        if even_width != width || even_height != height {
            tracing::info!(
                "Camera {}: rounded dimensions {}x{} → {even_width}x{even_height} for yuv420p",
                identity.label(),
                width,
                height,
            );
        }

        let mut child = FfmpegCommand::new()
            .overwrite()
            .format(&config.input_format)
            .codec_video(&config.input_codec)
            .size(even_width, even_height)
            .rate(target_fps)
            .input("pipe:0")
            .codec_video(&config.output_codec)
            .preset(&config.preset)
            .crf(config.crf)
            .pix_fmt(&config.pix_fmt)
            .no_audio()
            .output(output_path.to_string_lossy().as_ref())
            .spawn()
            .context("Failed to spawn ffmpeg")?;

        let stdin = child
            .take_stdin()
            .context("ffmpeg stdin not available")?;

        tracing::info!(
            "Camera {}: recording to {} ({}, {}, CRF {})",
            identity.label(),
            output_path.display(),
            config.output_codec,
            config.preset,
            config.crf,
        );

        Ok(Self {
            ffmpeg_child: child,
            stdin: Some(stdin),
            output_path,
            frame_count: 0,
            timestamps: Vec::new(),
        })
    }

    /// Spawn an ffmpeg subprocess from a pre-built config.
    ///
    /// Called by the recording thread's Setup handler. Delegates to `new()`
    /// but takes a single config struct, keeping the call site clean when
    /// processing a `Vec<RecorderSpawnConfig>`.
    pub fn spawn(config: RecorderSpawnConfig) -> anyhow::Result<Self> {
        Self::new(
            config.output_path,
            &config.identity,
            config.width,
            config.height,
            config.target_fps,
            &config.config,
        )
    }

    /// Write one MJPEG frame to ffmpeg's stdin.
    ///
    /// `data` is raw JPEG bytes. The frame is piped directly —
    /// ffmpeg decodes and re-encodes it.
    pub fn feed_frame(
        &mut self,
        data: &[u8],
        frame_number: i64,
        grab_timestamp_ns: i64,
        recorded_timestamp_ns: i64,
    ) -> anyhow::Result<()> {
        if let Some(ref mut stdin) = self.stdin {
            stdin
                .write_all(data)
                .context("Failed to write frame to ffmpeg stdin")?;
        } else {
            anyhow::bail!("VideoRecorder: stdin already closed (finish was called?)");
        }

        self.frame_count += 1;
        self.timestamps.push(FrameTimestamp {
            frame_number,
            grab_timestamp_ns,
            recorded_timestamp_ns,
        });

        Ok(())
    }

    /// Finalize the video: close stdin (EOF to ffmpeg), wait for encoding to
    /// complete, return all accumulated per-frame timestamps.
    pub fn finish(mut self) -> anyhow::Result<Vec<FrameTimestamp>> {
        tracing::info!(
            "Finishing recording: {} frames → {}",
            self.frame_count,
            self.output_path.display(),
        );

        // Drop stdin so ffmpeg sees EOF and writes the file trailer
        self.stdin.take();

        // Drain stderr internally (ffmpeg_sidecar's wait() handles this),
        // then block until ffmpeg exits
        self.ffmpeg_child
            .wait()
            .context("ffmpeg process failed")?;

        tracing::info!(
            "Recording complete: {} frames written to {}",
            self.timestamps.len(),
            self.output_path.display(),
        );

        // Prevent Drop from killing an already-exited ffmpeg
        self.frame_count = 0;
        Ok(std::mem::take(&mut self.timestamps))
    }

    pub fn frame_count(&self) -> u64 {
        self.frame_count
    }

    pub fn output_path(&self) -> &std::path::Path {
        &self.output_path
    }
}

impl Drop for VideoRecorder {
    fn drop(&mut self) {
        if self.frame_count > 0 {
            tracing::warn!(
                "VideoRecorder dropped with {} frames — killing ffmpeg. \
                 Partial file may remain: {}",
                self.frame_count,
                self.output_path.display(),
            );
        }
        let _ = self.ffmpeg_child.kill();
    }
}
