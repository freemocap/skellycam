//! High-precision monotonic performance counter.
//!
//! Returns i64 nanoseconds from an arbitrary but monotonic origin.
//! Equivalent to Python's `time.perf_counter_ns()`.
//! Not suitable for wall-clock time — use `TimebaseMapping` for UTC conversion.

use std::sync::OnceLock;
use std::time::Instant;

/// The `Instant` captured at process start.
/// Serves as the zero-point for our monotonic nanosecond counter.
static PROCESS_START: OnceLock<Instant> = OnceLock::new();

/// Return monotonic nanoseconds since process start.
///
/// Uses `std::time::Instant` which is:
/// - **Monotonic**: never goes backwards (NTP adjustments don't affect it)
/// - **High-resolution**: typically nanosecond or sub-microsecond precision
/// - **Cross-platform**: works on Windows, macOS, Linux
///
/// The returned value is relative to process start, not the Unix epoch.
/// Use `TimebaseMapping` to convert to UTC when needed.
pub fn performance_counter_nanoseconds() -> i64 {
    let start = PROCESS_START.get_or_init(Instant::now);
    start.elapsed().as_nanos() as i64
}
