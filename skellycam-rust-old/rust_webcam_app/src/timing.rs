//! Per-frame-stage timing accumulator.
//!
//! Prints microsecond averages for each pipeline stage every N frames so the
//! user can see where CPU time is going.
//!
//! ## Python analogy
//!
//! This is the Rust equivalent of using `time.perf_counter_ns()` around blocks
//! of code and printing a summary every N iterations.  The key difference:
//!
//! - In Python you'd store timing values in a list and `np.mean()` them.
//! - In Rust, we accumulate into `u128` (unsigned 128-bit integer) and divide
//!   once when printing.  This avoids allocating a list and avoids floating-point
//!   accumulation error over many frames.
//!
//! ## Why `&mut u128` instead of owned values?
//!
//! The accumulators live on the stack frame of `app::run()`.  We pass `&mut`
//! references so `print_timing` can reset them after printing.  This is the
//! same pattern as passing a mutable list to a function in Python, but Rust's
//! borrow checker guarantees no other code can read or write those accumulators
//! while `print_timing` holds the mutable reference.

/// How many frames between timing printouts.
pub(crate) const TIMING_INTERVAL: u64 = 60;

/// Print per-stage microsecond averages every `TIMING_INTERVAL` frames,
/// then reset all accumulators to zero.
///
/// Each accumulator tracks the **sum** of nanoseconds for one pipeline stage
/// across the interval.  The printout divides by the interval count and by
/// 1,000 to convert to microseconds.
pub(crate) fn print_timing(
    frame_index: u64,
    frames_per_second: f64,
    accumulated_keyboard: &mut u128,
    accumulated_rotation: &mut u128,
    accumulated_scale: &mut u128,
    accumulated_dimension_update: &mut u128,
    accumulated_record: &mut u128,
    accumulated_conversion: &mut u128,
    accumulated_buffer_update: &mut u128,
    accumulated_total: &mut u128,
) {
    if frame_index % TIMING_INTERVAL != 0 {
        return;
    }
    let interval_count = TIMING_INTERVAL as f64;
    let microseconds =
        |nanoseconds: u128| (nanoseconds as f64) / interval_count / 1_000.0;
    println!(
        "Frame {:>5} | keyboard: {:>9.3}µs  rotation: {:>8.3}µs  \
         scale: {:>8.3}µs  dimension: {:>8.3}µs  record: {:>8.3}µs  \
         conversion: {:>9.3}µs  buffer_update: {:>9.3}µs | {:>9.3}µs total  {:.0} FPS",
        frame_index,
        microseconds(*accumulated_keyboard),
        microseconds(*accumulated_rotation),
        microseconds(*accumulated_scale),
        microseconds(*accumulated_dimension_update),
        microseconds(*accumulated_record),
        microseconds(*accumulated_conversion),
        microseconds(*accumulated_buffer_update),
        microseconds(*accumulated_total),
        frames_per_second,
    );
    // Reset all accumulators for the next interval
    *accumulated_keyboard = 0;
    *accumulated_rotation = 0;
    *accumulated_scale = 0;
    *accumulated_dimension_update = 0;
    *accumulated_record = 0;
    *accumulated_conversion = 0;
    *accumulated_buffer_update = 0;
    *accumulated_total = 0;
}
