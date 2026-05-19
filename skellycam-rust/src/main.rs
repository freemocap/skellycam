//! SkellyCam Rust — camera test harness.
//!
//! IMPORTANT: Always use `cargo run --release` for real performance testing.
//!
//! Usage:
//!   cargo run --release -- test all [--max-cameras N]
//!   cargo run --release -- test detect
//!   cargo run --release -- test multi [--cameras N] [--indices 0,2,4] [--max-loops N]
//!   cargo run --release -- test manager [--cameras N]
//!   cargo run --release -- test recording [--cameras N] [--output PATH]
//!   cargo run --release -- test pause [--cameras N]
//!   cargo run --release -- test update <subcommand> [flags]

mod tests;

fn main() -> anyhow::Result<()> {
    if cfg!(debug_assertions) {
        tracing::warn!(
            "WARNING: Running in debug mode. Use `cargo run --release` for full performance.\n"
        );
    }
    skellycam::init_logging(skellycam::DEFAULT_LOG_LEVEL);

    let args: Vec<String> = std::env::args().collect();
    dispatch_command(&args)
}

fn dispatch_command(args: &[String]) -> anyhow::Result<()> {
    if args.iter().any(|arg| arg == "--serve") {
        return run_server();
    }

    match args.get(1).map(|s| s.as_str()) {
        Some("test") => match args.get(2).map(|s| s.as_str()) {
            Some("all") => tests::all_tests::run(&args[3..]),
            Some("recording") => tests::recording_tests::run(&args[3..]),
            Some("pause") => tests::pause_tests::run(&args[3..]),
            Some("rotate") => tests::rotation_tests::run(&args[3..]),
            Some("update") => tests::update_config_tests::run(&args[3..]),
            Some("multi") => tests::multi_camera_tests::run(&args[3..]),
            Some("manager") => tests::manager_tests::run(&args[3..]),
            Some("detect") => tests::detection_tests::run(&args[3..]),
            Some("lifecycle") => tests::lifecycle_tests::run(&args[3..]),
            Some(other) => {
                eprintln!("unknown test module: {other}");
                Ok(())
    }
            None => print_usage(),
        },
        _ => print_usage(),
    }
}

fn run_server() -> anyhow::Result<()> {
    use std::sync::atomic::Ordering;
    use std::sync::Arc;

    let state = Arc::new(skellycam::api::AppState::new());
    let router = skellycam::api::build_router(state.clone());

    let addr = "0.0.0.0:53117";
    eprintln!("══════════════════════════════════════════════════");
    eprintln!("  Skellycam Server");
    eprintln!("  http://localhost:53117");
    eprintln!("  Swagger docs: http://localhost:53117/docs");
    eprintln!("  Test page:    http://localhost:53117/test");
    eprintln!("  Press Ctrl+C to stop");
    eprintln!("══════════════════════════════════════════════════");

    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .enable_all()
        .build()?;

    rt.block_on(async {
        let listener = tokio::net::TcpListener::bind(addr).await?;

        let shutdown_flag = state.shutdown_flag.clone();
        axum::serve(listener, router)
            .with_graceful_shutdown(async move {
                tokio::select! {
                    _ = tokio::signal::ctrl_c() => {
                        eprintln!("\nCtrl+C received — shutting down...");
                    }
                    _ = async {
                        while !shutdown_flag.load(Ordering::SeqCst) {
                            tokio::time::sleep(std::time::Duration::from_millis(100)).await;
                        }
                    } => {
                        eprintln!("\n/shutdown called — shutting down...");
                    }
                }
            })
            .await?;

        Ok::<_, anyhow::Error>(())
    })?;

    // Close all camera groups on the way out
    state.camera_manager.blocking_lock().close_all_groups();

    eprintln!("Server stopped.");
    Ok(())
}

fn print_usage() -> anyhow::Result<()> {
    eprintln!("usage: cargo run --release -- [--serve] test <module> [flags]");
    eprintln!("modules:");
    eprintln!("  all        — run full test suite (1 camera → N cameras)");
    eprintln!("  detect     — enumerate cameras");
    eprintln!("  lifecycle  — start → stream → shutdown test");
    eprintln!("  multi      — multi-camera lockstep streaming");
    eprintln!("  manager    — CameraGroupManager lifecycle");
    eprintln!("  recording  — full recording lifecycle test");
    eprintln!("  pause      — pause/unpause/toggle test");
    eprintln!("  rotate     — lossless JPEG rotation test (0/90/180/270 + record)");
    eprintln!("  update     — config update tests (exposure, resolution, framerate, add-camera, remove-camera)");
    Ok(())
}
