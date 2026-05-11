//! Polars-based CSV reader for post-recording analysis.
//! Loads per-camera timestamp CSVs into DataFrames,
//! builds multi-frame DataFrame via joins, computes cross-camera statistics.

pub struct TimestampCsvReader {}

impl TimestampCsvReader {
    pub fn new() -> Self {
        Self {}
    }
}
