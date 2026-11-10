//! Per-camera video recorder: ffmpeg subprocess fed MJPEG frames via stdin.
//!
//! Each VideoRecorder spawns an ffmpeg child process that reads MJPEG frames
//! from `pipe:0`, decodes them, and re-encodes to H.264. Frames are fed via
//! `feed_frame()`. `finish()` closes stdin (EOF to ffmpeg) and returns
//! per-frame timestamps.

use std::collections::VecDeque;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::ChildStdin;
use std::thread::JoinHandle;

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
            preset: "ultrafast".into(),
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
    /// Reads ffmpeg's stderr for the whole recording; returns its last lines.
    stderr_reader: Option<JoinHandle<FfmpegStderr>>,
    output_path: PathBuf,
    frame_count: u64,
    timestamps: Vec<FrameTimestamp>,
}

static FFMPEG_PATH: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();

/// Embedded applications supply their bundled encoder [@ffmpegSidecarCommand].
pub fn configure_ffmpeg_path(path: PathBuf) -> anyhow::Result<()> {
    let path = path.canonicalize().context("FFmpeg executable is missing")?;
    if !path.is_file() { anyhow::bail!("FFmpeg path is not a file"); }
    if let Some(existing) = FFMPEG_PATH.get() {
        if existing != &path { anyhow::bail!("FFmpeg was already configured with another executable"); }
    } else {
        FFMPEG_PATH.set(path).map_err(|_| anyhow::anyhow!("FFmpeg configuration raced another caller"))?;
    }
    Ok(())
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

        if output_path.exists() {
            anyhow::bail!("Refusing to overwrite recording {}", output_path.display());
        }
        let mut command = match FFMPEG_PATH.get() {
            Some(path) => FfmpegCommand::new_with_path(path),
            None => FfmpegCommand::new(),
        };
        let mut child = command
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

        // FfmpegCommand pipes stderr at `-loglevel level+info`, and FfmpegChild drains it only
        // inside wait() [@ffmpegSidecarChildPipes]. ffmpeg can log on every frame (a warning per
        // frame for some cameras' MJPEG APP segments); once the unread pipe fills, ffmpeg stops
        // reading stdin and feed_frame blocks. Read stderr for the whole recording instead.
        // stdout stays piped as FfmpegChild requires; ffmpeg writes the video to `output_path`
        // and nothing to stdout.
        let stderr = child.take_stderr().context("ffmpeg stderr not available")?;
        let stderr_label = identity.label();
        let stderr_reader = match std::thread::Builder::new()
            .name(format!("ffmpeg-stderr-{}", identity.camera_id))
            .spawn(move || read_ffmpeg_stderr(stderr, &stderr_label))
        {
            Ok(reader) => reader,
            Err(error) => {
                let _ = child.kill();
                return Err(error).context("Failed to spawn ffmpeg stderr reader");
            }
        };

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
            stderr_reader: Some(stderr_reader),
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

        // Block until ffmpeg exits; the reader thread ends when ffmpeg closes stderr.
        let status = self.ffmpeg_child
            .wait()
            .context("ffmpeg process failed")?;
        let stderr_tail = self.stderr_reader
            .take()
            .and_then(|reader| reader.join().ok())
            .map(|stderr| stderr.tail)
            .unwrap_or_default();
        if !status.success() {
            anyhow::bail!(
                "ffmpeg failed with {status}: {}\nLast ffmpeg output:\n{}",
                self.output_path.display(),
                Vec::from(stderr_tail).join("\n"),
            );
        }

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

/// Lines of ffmpeg output kept for the error report when encoding fails.
const STDERR_TAIL_LINES: usize = 40;
/// Longest stored line; ffmpeg's lines are short, this only bounds malformed output.
const STDERR_MAX_LINE_BYTES: usize = 1024;
/// Distinct ffmpeg warning/error messages logged per recording; any beyond this are only counted.
const STDERR_MAX_DISTINCT_PROBLEMS: usize = 16;

/// What ffmpeg wrote to stderr during one recording.
#[derive(Default)]
struct FfmpegStderr {
    /// The last lines, for the error report when encoding fails.
    tail: VecDeque<String>,
    /// Each distinct warning/error message with its number of occurrences.
    problems: Vec<FfmpegProblem>,
    /// Warning/error lines beyond `STDERR_MAX_DISTINCT_PROBLEMS` distinct messages.
    unlisted_problems: u64,
}

struct FfmpegProblem {
    context: String,
    level: String,
    message: String,
    count: u64,
}

/// One `-loglevel level+...` line: `[level] message` or `[context @ pointer] [level] message`.
struct FfmpegLogLine<'a> {
    context: &'a str,
    level: &'a str,
    message: &'a str,
}

fn parse_ffmpeg_log_line(line: &str) -> Option<FfmpegLogLine<'_>> {
    let (context, rest) = match line.strip_prefix('[').and_then(|after| after.split_once("] ")) {
        Some((tag, rest)) if tag.contains(" @ ") => (tag.split(" @ ").next().unwrap_or(""), rest),
        _ => ("", line),
    };
    let (level, message) = rest.strip_prefix('[')?.split_once(']')?;
    Some(FfmpegLogLine { context, level, message: message.trim_start() })
}

/// Read ffmpeg's stderr until ffmpeg closes it.
///
/// ffmpeg can repeat one warning or error on every frame, so each distinct message is logged
/// once and its repeats are counted and reported when the recording ends. Lines end at `\n` or
/// `\r`, because ffmpeg ends progress lines with `\r`.
fn read_ffmpeg_stderr(mut stderr: impl Read, label: &str) -> FfmpegStderr {
    let mut output = FfmpegStderr { tail: VecDeque::with_capacity(STDERR_TAIL_LINES), ..Default::default() };
    let mut line = Vec::with_capacity(256);
    let mut buffer = [0u8; 8192];
    loop {
        let read = match stderr.read(&mut buffer) {
            Ok(0) | Err(_) => break,
            Ok(read) => read,
        };
        for &byte in &buffer[..read] {
            if byte == b'\n' || byte == b'\r' {
                finish_stderr_line(&mut line, &mut output, label);
            } else if line.len() < STDERR_MAX_LINE_BYTES {
                line.push(byte);
            }
        }
    }
    finish_stderr_line(&mut line, &mut output, label);
    for problem in output.problems.iter().filter(|problem| problem.count > 1) {
        tracing::warn!(
            "ffmpeg {label}: {} more lines of [{}] [{}] {}",
            problem.count - 1, problem.context, problem.level, problem.message,
        );
    }
    if output.unlisted_problems > 0 {
        tracing::warn!("ffmpeg {label}: {} other warning or error lines", output.unlisted_problems);
    }
    output
}

fn finish_stderr_line(line: &mut Vec<u8>, output: &mut FfmpegStderr, label: &str) {
    if line.is_empty() {
        return;
    }
    let text = String::from_utf8_lossy(line).into_owned();
    line.clear();
    if let Some(parsed) = parse_ffmpeg_log_line(&text) {
        if matches!(parsed.level, "warning" | "error" | "fatal" | "panic") {
            note_ffmpeg_problem(output, &parsed, label);
        }
    }
    if output.tail.len() == STDERR_TAIL_LINES {
        output.tail.pop_front();
    }
    output.tail.push_back(text);
}

/// Log a warning/error message the first time it appears; count it afterwards.
///
/// ffmpeg keeps encoding after these lines. A recording that fails is reported by ffmpeg's
/// exit status in `finish()` or by a failed write in `feed_frame()`.
fn note_ffmpeg_problem(output: &mut FfmpegStderr, line: &FfmpegLogLine<'_>, label: &str) {
    let known = output.problems.iter_mut().find(|known| {
        known.message == line.message && known.context == line.context && known.level == line.level
    });
    if let Some(known) = known {
        known.count += 1;
    } else if output.problems.len() < STDERR_MAX_DISTINCT_PROBLEMS {
        tracing::warn!(
            "ffmpeg {label}: [{}] [{}] {} (repeats are counted, not logged)",
            line.context, line.level, line.message,
        );
        output.problems.push(FfmpegProblem {
            context: line.context.into(),
            level: line.level.into(),
            message: line.message.into(),
            count: 1,
        });
    } else {
        output.unlisted_problems += 1;
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stderr_reader_reads_to_the_end_and_keeps_the_last_lines() {
        // More output than a pipe buffer holds, shaped like ffmpeg's per-frame MJPEG errors
        // and `\r`-terminated progress lines.
        let mut log = String::from("[info] ffmpeg version 7.1\n");
        for frame in 1..=5000 {
            log.push_str(&format!(
                "[mjpeg @ 000002C7070CDAC0] [error] unable to decode APP fields\n[info] frame={frame}\r"
            ));
        }
        let output = read_ffmpeg_stderr(log.as_bytes(), "test camera");
        assert_eq!(output.tail.len(), STDERR_TAIL_LINES);
        assert_eq!(output.tail.back().map(String::as_str), Some("[info] frame=5000"));
    }

    #[test]
    fn a_message_repeated_on_every_frame_is_one_problem_with_a_count() {
        // The decoder context's address can differ between ffmpeg's decoder threads.
        let mut log = String::new();
        for frame in 0..3600 {
            let address = if frame % 2 == 0 { "000002C7070CDAC0" } else { "000002C7070CE000" };
            log.push_str(&format!("[mjpeg @ {address}] [error] unable to decode APP fields\n"));
        }
        log.push_str("[swscaler @ 000002083BFDB200] [warning] deprecated pixel format used\n");
        let output = read_ffmpeg_stderr(log.as_bytes(), "test camera");
        let problems: Vec<_> = output.problems.iter()
            .map(|problem| (problem.context.as_str(), problem.level.as_str(), problem.count))
            .collect();
        assert_eq!(problems, [("mjpeg", "error", 3600), ("swscaler", "warning", 1)]);
        assert_eq!(output.unlisted_problems, 0);
    }

    #[test]
    fn distinct_problem_messages_are_bounded() {
        let log: String = (0..100).map(|frame| format!("[error] corrupt frame {frame}\n")).collect();
        let output = read_ffmpeg_stderr(log.as_bytes(), "test camera");
        assert_eq!(output.problems.len(), STDERR_MAX_DISTINCT_PROBLEMS);
        assert_eq!(output.unlisted_problems, 100 - STDERR_MAX_DISTINCT_PROBLEMS as u64);
    }

    #[test]
    fn stderr_reader_bounds_line_length() {
        let log = vec![b'x'; 10 * STDERR_MAX_LINE_BYTES];
        let output = read_ffmpeg_stderr(log.as_slice(), "test camera");
        assert_eq!(output.tail.len(), 1);
        assert_eq!(output.tail[0].len(), STDERR_MAX_LINE_BYTES);
    }

    #[test]
    fn log_lines_parse_with_and_without_a_context_prefix() {
        let parts = |line| parse_ffmpeg_log_line(line).map(|parsed| (parsed.context, parsed.level, parsed.message));
        assert_eq!(parts("[info] frame=1"), Some(("", "info", "frame=1")));
        assert_eq!(parts("[mjpeg @ 000002C7] [error] unable to decode APP fields"),
                   Some(("mjpeg", "error", "unable to decode APP fields")));
        assert_eq!(parts("[out#0/mp4 @ 000001D4] [fatal] Error opening output"),
                   Some(("out#0/mp4", "fatal", "Error opening output")));
        assert_eq!(parts("plain text"), None);
    }
}
