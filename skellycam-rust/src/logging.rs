//! Custom [`tracing`] event formatter producing skellylogs-style pipe-delimited
//! log lines.  Mirrors the format defined in the Python `skellylogs` package.
//!
//! Output format:
//! ```text
//! >> {message} |  {level} |  {delta_ms}ms |  {target}:{line} |  {timestamp} |  PID:{pid}:{proc_name} |  TID:{tid}:{thread_name}
//! ```

use std::fmt;
use std::sync::Mutex;
use std::time::Instant;

use chrono::Local;
use tracing::{Event, Subscriber};
use tracing_subscriber::fmt::format::Writer;
use tracing_subscriber::fmt::{FmtContext, FormatEvent, FormatFields};
use tracing_subscriber::registry::LookupSpan;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Custom event formatter that mimics the `skellylogs` Python logger output.
///
/// Each event is written as a single pipe-delimited line:
///
/// ```text
/// >> camera cam-0: capture loop started |  INFO |  0.123ms |  skellycam::camera::camera_thread:208 |  2026-05-20T14:30:01.123 |  PID:12345:skellycam |  TID:7:cam-0
/// ```
pub(crate) struct SkellyFormat {
    /// The [`Instant`] of the previous event — used to compute the `delta_ms`
    /// field that appears between the level and the target.
    prev_time: Mutex<Instant>,

    /// Cached process name (extracted from the executable path once).
    process_name: String,
}

impl SkellyFormat {
    pub(crate) fn new() -> Self {
        let process_name = std::env::current_exe()
            .ok()
            .and_then(|p| p.file_stem()?.to_str().map(String::from))
            .unwrap_or_else(|| "unknown".to_string());

        Self {
            prev_time: Mutex::new(Instant::now()),
            process_name,
        }
    }
}

impl<S, N> FormatEvent<S, N> for SkellyFormat
where
    S: Subscriber + for<'a> LookupSpan<'a>,
    N: for<'a> FormatFields<'a> + 'static,
{
    fn format_event(
        &self,
        ctx: &FmtContext<'_, S, N>,
        mut writer: Writer<'_>,
        event: &Event<'_>,
    ) -> fmt::Result {
        let metadata = event.metadata();
        let now = Instant::now();

        // ── Delta time ────────────────────────────────────────────
        let delta_ms = {
            let mut prev = self.prev_time.lock().unwrap();
            let delta = now.duration_since(*prev);
            *prev = now;
            format_delta(delta)
        };

        // ── Timestamp ─────────────────────────────────────────────
        let ts = Local::now().format("%Y-%m-%dT%H:%M:%S%.3f");

        // ── Thread identity ───────────────────────────────────────
        let current_thread = std::thread::current();
        let tid = format_thread_id(current_thread.id());
        let tname = current_thread.name().unwrap_or("unnamed");

        // ── Location ──────────────────────────────────────────────
        let target = metadata.target();
        let loc = metadata
            .line()
            .map(|l| format!(":{l}"))
            .unwrap_or_default();

        // ── Level (padded to 5 chars) ─────────────────────────────
        let level_padded = pad_level(metadata.level().as_str());

        // ── PID ───────────────────────────────────────────────────
        let pid = std::process::id();

        // ── Write the header ──────────────────────────────────────
        // >> {message} |  {level} |  {delta}ms |  {target}:{line} |  {ts} |  PID:{pid}:{pname} |  TID:{tid}:{tname}
        write!(writer, ">> ")?;

        // Delegate message formatting to the configured field
        // formatter (normally [`format::Full`]). This writes the
        // human-readable message with all template fields interpolated.
        ctx.field_format().format_fields(writer.by_ref(), event)?;

        write!(
            writer,
            " |  {level_padded} |  {delta_ms} |  {target}{loc} |  {ts} |  PID:{pid}:{} |  TID:{tid}:{tname}\n",
            self.process_name,
        )
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Format a [`std::time::Duration`] as milliseconds with three decimal places,
/// e.g. `"0.123ms"`.
fn format_delta(d: std::time::Duration) -> String {
    format!("{:.3}ms", d.as_secs_f64() * 1000.0)
}

/// Pad a level name to 5 characters for column alignment.
///
/// ```text
/// TRACE -> "TRACE"
/// DEBUG -> "DEBUG"
/// INFO  -> "INFO "
/// WARN  -> "WARN "
/// ERROR -> "ERROR"
/// ```
fn pad_level(level: &str) -> String {
    format!("{level:<5}")
}

/// Format a [`std::thread::ThreadId`] as a plain integer string.
///
/// The standard `Display` impl produces `ThreadId(7)` — we strip the
/// prefix and suffix to get just `7`.
fn format_thread_id(id: std::thread::ThreadId) -> String {
    let raw = format!("{:?}", id);
    raw.trim_start_matches("ThreadId(")
        .trim_end_matches(')')
        .to_string()
}
