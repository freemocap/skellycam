//! External-process video recording via ffmpeg.
//!
//! Spawns an `ffmpeg` child process and pipes raw RGB24 frames to its stdin.
//! ffmpeg handles all encoding (H.264 → MP4 container) so the Rust side stays
//! simple: just write bytes.
//!
//! ## Python analogy
//!
//! This is exactly the same pattern as:
//! ```python
//! import subprocess
//! proc = subprocess.Popen(
//!     ["ffmpeg", ..., "pipe:0"],
//!     stdin=subprocess.PIPE,
//! )
//! proc.stdin.write(rgb_bytes)
//! # ...
//! proc.stdin.close()
//! proc.wait()
//! ```
//!
//! ## Key Rust differences from Python's subprocess
//!
//! 1. **Ownership of the child handle**: `Child` is a resource that *must* be
//!    waited on (or killed) to avoid zombie processes.  Rust makes this explicit
//!    — the compiler warns if you drop a `Child` without calling `wait()`.
//!
//! 2. **`Option<ChildStdin>`**: `stdin.take()` temporarily moves ownership out
//!    of the struct (leaving `None`).  This is how we close the pipe to signal
//!    EOF to ffmpeg.  Python's `proc.stdin.close()` does the same thing, but
//!    in Rust the ownership dance is visible in the type system.
//!
//! 3. **Drop safety net**: The `Drop` impl runs when a `VideoRecorder` is
//!    destroyed, even if `finish()` was never called (e.g., during an early
//!    exit or panic).  In Python you'd use a `try/finally` or context manager.
//!    Rust's `Drop` is like `__del__`, but deterministic and guaranteed to run.

use anyhow::{Context, Result};
use std::io::Write;
use std::process::{Child, ChildStdin, Command, Stdio};

/// Records webcam frames to a video file by piping raw RGB data to an ffmpeg subprocess.
///
/// ## Fields
///
/// - `child`: The spawned ffmpeg process handle.
/// - `stdin`: The write end of ffmpeg's stdin pipe, wrapped in `Option` so we
///   can `.take()` it to signal EOF when recording stops.
/// - `frame_count`: How many frames have been fed so far (for final summary).
///
/// Requires `ffmpeg` to be installed and available on the system PATH.
pub struct VideoRecorder {
    child: Child,
    stdin: Option<ChildStdin>,
    frame_count: u64,
}

impl VideoRecorder {
    /// Begin recording.
    ///
    /// Spawns an ffmpeg process configured for raw RGB24 input on stdin,
    /// encoding to H.264 (libx264) with `ultrafast` preset and `yuv420p`
    /// pixel format for broad compatibility.
    ///
    /// ## ffmpeg argument breakdown
    ///
    /// | Flag | Meaning |
    /// |------|---------|
    /// | `-y` | Overwrite output file without asking |
    /// | `-f rawvideo` | Input format: raw video (no container) |
    /// | `-pixel_format rgb24` | 3 bytes per pixel: R, G, B |
    /// | `-video_size WxH` | Frame dimensions |
    /// | `-framerate N` | Frames per second |
    /// | `-i pipe:0` | Read from stdin |
    /// | `-c:v libx264` | Video codec: H.264 |
    /// | `-pix_fmt yuv420p` | Output pixel format (broad player compatibility) |
    /// | `-preset ultrafast` | Encode speed over compression ratio |
    /// | `-crf 23` | Constant Rate Factor (quality, lower = better) |
    pub fn start(width: u32, height: u32, frames_per_second: u32, output_path: &str) -> Result<Self> {
        let size = format!("{width}x{height}");
        let rate = frames_per_second.to_string();

        let mut child = Command::new("ffmpeg")
            .args([
                "-y",
                "-f", "rawvideo",
                "-pixel_format", "rgb24",
                "-video_size", &size,
                "-framerate", &rate,
                "-i", "pipe:0",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "ultrafast",
                "-crf", "23",
                output_path,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::inherit())
            .spawn()
            .context(
                "Failed to launch ffmpeg. Make sure ffmpeg is installed and on your PATH.",
            )?;

        // `.take()` moves the stdin handle out of `child`, leaving `child.stdin` as None.
        // This is necessary because we need to own the stdin writer separately from
        // the child process handle.
        let stdin = child
            .stdin
            .take()
            .context("Failed to open ffmpeg stdin pipe.")?;

        Ok(Self {
            child,
            stdin: Some(stdin),
            frame_count: 0,
        })
    }

    /// Feed one raw RGB24 frame to the encoder.
    ///
    /// `rgb_data` must be a byte slice of length `width × height × 3` with
    /// pixels in row-major R, G, B order (no alpha, no padding).
    ///
    /// ## Write semantics
    ///
    /// `std::io::Write::write_all` is like Python's `file.write()` on a
    /// binary file opened with `wb` — it writes all bytes or returns an error.
    /// The `&[u8]` slice is a borrowed view into the image buffer; no copy
    /// happens at the Rust level (the OS may buffer).
    pub fn feed_frame(&mut self, rgb_data: &[u8]) -> Result<()> {
        if let Some(stdin) = self.stdin.as_mut() {
            stdin
                .write_all(rgb_data)
                .context("Failed to write frame — the ffmpeg process may have terminated unexpectedly.")?;
            self.frame_count += 1;
        }
        Ok(())
    }

    /// Finish encoding: close the stdin pipe and wait for ffmpeg to exit.
    ///
    /// `self.stdin.take()` moves the `ChildStdin` out and drops it, which
    /// closes the write end of the pipe.  ffmpeg sees EOF and finishes
    /// encoding.  We then wait for the process to exit and check its status.
    ///
    /// ## Python equivalent:
    /// ```python
    /// proc.stdin.close()
    /// returncode = proc.wait()
    /// if returncode != 0:
    ///     raise RuntimeError(...)
    /// ```
    ///
    /// ## Why `mut self` instead of `&mut self`?
    ///
    /// `mut self` means this method **consumes** the `VideoRecorder` — after
    /// calling `finish()`, the caller can no longer use that recorder.  This
    /// prevents accidentally feeding frames after finishing.  Python can't
    /// express this at the type level.
    pub fn finish(mut self) -> Result<()> {
        // Dropping stdin signals EOF to ffmpeg
        drop(self.stdin.take());
        let status = self
            .child
            .wait()
            .context("Failed to wait for ffmpeg to finish.")?;

        if status.success() {
            println!(
                "\nRecording complete: {} frames saved.",
                self.frame_count
            );
        } else {
            let code = status.code().unwrap_or(-1);
            anyhow::bail!(
                "ffmpeg exited with error code {code}. The output file may be corrupt."
            );
        }
        Ok(())
    }
}

/// Safety-net destructor: if `finish()` is never called (early exit, panic,
/// etc.), close stdin and kill ffmpeg to prevent zombies.
///
/// ## Python equivalent:
/// ```python
/// def __del__(self):
///     if self.stdin:
///         self.stdin.close()
///     if self.child.poll() is None:
///         self.child.kill()
///         self.child.wait()
/// ```
///
/// But Rust's `Drop` is deterministic (it runs when the value goes out of
/// scope), unlike Python's `__del__` which may never run due to GC cycles.
impl Drop for VideoRecorder {
    fn drop(&mut self) {
        // Close stdin so ffmpeg can finish, then kill the process
        drop(self.stdin.take());
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
