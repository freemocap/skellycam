//! Performance counter — the single canonical T=0 anchor and elapsed-nanosecond
//! reader used by every timestamping site in the pipeline.
//!
//! T=0 is defined as the wall-clock moment `anchor_performance_clock()` was
//! first called. By design, that single call is made from `init_logging()` in
//! `lib.rs`, so every entry path (binary `main`, the PyO3 bridge, integration
//! tests) anchors at the same moment without needing to remember to call this
//! module directly.
//!
//! All values returned by `performance_counter_nanoseconds()` are nanoseconds
//! since that anchor, measured by `std::time::Instant` — monotonic, immune to
//! NTP slew, DST, and leap seconds. The wall-clock equivalent of T=0 is
//! captured simultaneously via `SystemTime::now()` so the statistics block
//! can print "T=0 anchored at YYYY-MM-DDTHH:MM:SS.sssZ" for correlation with
//! external logs.

use std::sync::OnceLock;
use std::time::{Instant, SystemTime};

struct ClockAnchor {
    monotonic: Instant,
    wall_clock: SystemTime,
}

static ANCHOR: OnceLock<ClockAnchor> = OnceLock::new();

/// Establishes T=0 for the performance clock. Called automatically by
/// `init_logging`; do not call from anywhere else.
///
/// Idempotent — the first call wins, subsequent calls are no-ops. The pair
/// `(Instant::now(), SystemTime::now())` is captured atomically inside the
/// closure that `OnceLock::get_or_init` runs exactly once.
pub fn anchor_performance_clock() {
    ANCHOR.get_or_init(|| ClockAnchor {
        monotonic: Instant::now(),
        wall_clock: SystemTime::now(),
    });
}

/// Nanoseconds since `anchor_performance_clock()` was first called.
///
/// If the anchor has somehow not been initialized (e.g. a test bypasses
/// `init_logging`), the anchor is established lazily here so the call still
/// returns a sensible value. Debug builds assert on that fallback path so the
/// missing-anchor case is caught during development.
pub fn performance_counter_nanoseconds() -> i64 {
    let anchor = ANCHOR.get_or_init(|| {
        debug_assert!(
            false,
            "performance clock read before init_logging() was called; \
             call skellycam::init_logging() at program entry"
        );
        ClockAnchor {
            monotonic: Instant::now(),
            wall_clock: SystemTime::now(),
        }
    });
    anchor.monotonic.elapsed().as_nanos() as i64
}

/// Returns the system wall-clock time that corresponds to T=0, for printing
/// in statistics headers (e.g. "T=0 anchored at 2026-05-18T14:57:38.646Z").
/// Returns `None` only if `anchor_performance_clock()` has never been called.
pub fn anchor_wall_clock_time() -> Option<SystemTime> {
    ANCHOR.get().map(|a| a.wall_clock)
}
