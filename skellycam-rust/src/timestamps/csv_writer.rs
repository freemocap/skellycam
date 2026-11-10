//! Streaming CSV writer: one row per frame, written during recording.
//!
//! Crash-resilient: data is flushed to disk alongside the video, so
//! timestamps survive even if the process exits before `finish()`.

use std::fs::File;
use std::path::PathBuf;

use anyhow::Context;

use crate::camera::FrameLifecycleTimestamps;

pub struct CsvWriter {
    writer: csv::Writer<File>,
    path: PathBuf,
    row_count: u64,
}

impl CsvWriter {
    /// Create a new CSV file at `path` and write the header row.
    ///
    /// Columns are this backend's frame lifecycle events in perf-counter nanoseconds.
    /// `pre_frame_grab_ns` / `post_frame_grab_ns` are the frame-grab bracket shared with
    /// SkellyCam's OpenCV backend: the capture loop starts waiting for the next frame
    /// (barrier exit) / the next frame is available to the loop (first poll with
    /// `Cap_hasNewFrame` true). The other columns are events only this backend has.
    /// SkellyCam's Python recording finalizer rewrites this file in the standard
    /// per-camera timestamps layout, keeping these events.
    pub fn new(path: PathBuf) -> anyhow::Result<Self> {
        let writer = csv::Writer::from_path(&path)
            .context("Failed to create timestamp CSV file")?;

        let mut writer = writer;
        writer
            .write_record(&[
                "frame_number",
                "pre_frame_grab_ns",
                "post_frame_grab_ns",
                "copied_from_driver_ns",
                "sent_to_multiframe_ns",
                "received_by_multiframe_ns",
                "pre_write_to_video_encoder_ns",
                "post_write_to_video_encoder_ns",
            ])
            .context("Failed to write CSV header")?;
        writer
            .flush()
            .context("Failed to flush CSV header")?;

        Ok(Self {
            writer,
            path,
            row_count: 0,
        })
    }

    /// Append one row to the CSV file and flush immediately.
    /// Flushing on every write ensures crash-resilience at the cost of
    /// slightly higher I/O — acceptable at 30fps per camera.
    pub fn write_row(
        &mut self,
        frame_number: i64,
        timestamps: &FrameLifecycleTimestamps,
        pre_record_ns: i64,
        post_record_ns: i64,
    ) -> anyhow::Result<()> {
        self.writer
            .write_record(&[
                frame_number.to_string(),
                timestamps.loop_start_ns.to_string(),
                timestamps.frame_available_ns.to_string(),
                timestamps.post_jpeg_extract_ns.to_string(),
                timestamps.pre_send_ns.to_string(),
                timestamps.gatherer_received_ns.to_string(),
                pre_record_ns.to_string(),
                post_record_ns.to_string(),
            ])
            .context("Failed to write CSV row")?;
        self.writer.flush().context("Failed to flush CSV row")?;

        self.row_count += 1;
        Ok(())
    }

    pub fn row_count(&self) -> u64 {
        self.row_count
    }

    /// Flush and return the file path for later use by the finalizer.
    pub fn finish(mut self) -> anyhow::Result<PathBuf> {
        self.writer.flush().context("Failed to flush CSV on finish")?;
        Ok(self.path)
    }
}
