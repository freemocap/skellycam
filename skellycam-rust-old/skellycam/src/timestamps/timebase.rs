//! TimebaseMapping: maps arbitrary perf_counter timebase to UTC Unix time.
//! Captured once at camera group startup, embedded in every frame's metadata.

/// Maps the arbitrary monotonic clock to UTC Unix nanoseconds.
#[derive(Debug, Clone, Copy)]
pub struct TimebaseMapping {
    /// UTC time in nanoseconds when this mapping was created.
    pub utc_time_nanoseconds: i64,
    /// Monotonic perf_counter value at the same instant.
    pub perf_counter_nanoseconds: i64,
    /// Offset from UTC to local time, in seconds.
    pub local_time_utc_offset_seconds: i32,
}

impl TimebaseMapping {
    /// Convert a perf_counter timestamp to Unix nanoseconds.
    pub fn to_unix_nanoseconds(&self, perf_counter: i64, local_time: bool) -> i64 {
        let unix = self.utc_time_nanoseconds + (perf_counter - self.perf_counter_nanoseconds);
        if local_time {
            unix + (self.local_time_utc_offset_seconds as i64 * 1_000_000_000)
        } else {
            unix
        }
    }
}
