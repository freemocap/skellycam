pub mod camera;
pub mod camera_group;
pub mod camera_group_manager;
pub mod recording;
pub mod timestamps;
pub mod frontend_payload;
pub mod pyo3_bridge;

/// Default log level for the entire process.
///
/// Change this to "trace" for hot-loop debugging, "debug" for
/// per-cycle diagnostics, "info" for normal operation.
/// `RUST_LOG` env var overrides this if set.
pub const DEFAULT_LOG_LEVEL: &str = "trace";

/// Initialize the tracing subscriber once for the entire process.
///
/// `try_init()` is a no-op on subsequent calls — safe to call from
/// both `main.rs` and the PyO3 bridge.
pub fn init_logging(log_level: &str) {
    use tracing_subscriber::EnvFilter;

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(log_level));

    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .try_init();
}
