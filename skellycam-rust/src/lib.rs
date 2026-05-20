pub mod api;
pub mod camera;
pub mod camera_group;
pub mod camera_group_manager;
pub mod decode;
pub mod logging;
pub mod recording;
pub mod timestamps;
pub mod frontend_payload;
pub mod pyo3_bridge;
pub mod websocket;

/// Default log level for the entire process.
///
/// Change this to "trace" for hot-loop debugging, "debug" for
/// per-cycle diagnostics, "info" for normal operation.
/// `RUST_LOG` env var overrides this if set.
pub const DEFAULT_LOG_LEVEL: &str = "debug"; //debuf is the default log level - showing a lot of non-looping details
// pub const DEFAULT_LOG_LEVEL: &str = "trace";// (trace turns on logs in the hot loop, which is very verbose but useful for debugging)

/// Initialize the tracing subscriber once for the entire process AND anchor
/// the performance clock at T=0.
///
/// This is the **single canonical T=0 anchor site** for the whole pipeline.
/// Every entry path (binary `main`, PyO3 module init, integration tests)
/// calls this, so the performance clock is always anchored before any
/// timestamping subsystem runs — no separate clock-anchor call required
/// at any other site.
///
/// Both `try_init()` (logging) and `anchor_performance_clock()` (timestamps)
/// are idempotent — subsequent calls are no-ops.
pub fn init_logging(log_level: &str) {
    use tracing_subscriber::EnvFilter;

    timestamps::performance::anchor_performance_clock();

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(log_level));

    let format = logging::SkellyFormat::new();

    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .event_format(format)
        .try_init();
}
