//! Streaming CSV writer for per-frame timestamp logging.
//! Writes one row per frame as recording progresses — data on disk
//! alongside the video, resilient to crashes.

pub struct TimestampCsvWriter {}

impl TimestampCsvWriter {
    pub fn new() -> Self {
        Self {}
    }
}
