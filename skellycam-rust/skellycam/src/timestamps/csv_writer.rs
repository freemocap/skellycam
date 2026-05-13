//! Streaming CSV writer: one row per frame, written during recording.
//!
//! Crash-resilient: data is flushed to disk alongside the video, so
//! timestamps survive even if the process exits before `finish()`.

use std::fs::File;
use std::path::PathBuf;

use anyhow::Context;

pub struct CsvWriter {
    writer: csv::Writer<File>,
    path: PathBuf,
    row_count: u64,
}

impl CsvWriter {
    /// Create a new CSV file at `path` and write the header row.
    /// Column names use full words — no abbreviations.
    pub fn new(path: PathBuf) -> anyhow::Result<Self> {
        let writer = csv::Writer::from_path(&path)
            .context("Failed to create timestamp CSV file")?;

        let mut writer = writer;
        writer
            .write_record(&[
                "frame_number",
                "grab_timestamp_nanoseconds",
                "recorded_timestamp_nanoseconds",
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
        grab_timestamp_nanoseconds: i64,
        recorded_timestamp_nanoseconds: i64,
    ) -> anyhow::Result<()> {
        self.writer
            .write_record(&[
                frame_number.to_string(),
                grab_timestamp_nanoseconds.to_string(),
                recorded_timestamp_nanoseconds.to_string(),
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
