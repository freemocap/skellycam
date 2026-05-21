//! SkellyCam Rust — camera test harness.
//!
//! IMPORTANT: Always use `cargo run --release` for real performance testing.
//!
//! Usage:
//!   cargo run --release -- --help
//!   cargo run --release -- test all --max-cameras N
//!   cargo run --release -- test detect
//!   cargo run --release -- test lifecycle --cameras N
//!   cargo run --release -- test multi --cameras N --max-loops N
//!   cargo run --release -- test recording --cameras N --output PATH
//!   cargo run --release -- test pause --cameras N
//!   cargo run --release -- test update --help
//!   cargo run --release -- --serve

use clap::Parser;

mod cli;
mod tests;

fn main() -> anyhow::Result<()> {
    if cfg!(debug_assertions) {
        tracing::warn!(
            "WARNING: Running in debug mode. Use `cargo run --release` for full performance.\n"
        );
    }
    skellycam::init_logging(skellycam::DEFAULT_LOG_LEVEL);

    let cli = cli::Cli::parse();
    dispatch_cli(cli)
}

fn dispatch_cli(cli: cli::Cli) -> anyhow::Result<()> {
    if cli.serve {
        return run_server();
    }
    match cli.command {
        Some(cli::Commands::Test { module }) => dispatch_test(module),
        Some(cli::Commands::Serve) => run_server(),
        None => Ok(()), // clap already printed help
    }
}

fn dispatch_test(module: cli::TestModule) -> anyhow::Result<()> {
    use cli::TestModule;
    match module {
        TestModule::All(a) => tests::all_tests::run(&a),
        TestModule::Detect => tests::detection_tests::run(),
        TestModule::Lifecycle(a) => tests::lifecycle_tests::run(&a),
        TestModule::Multi(a) => tests::multi_camera_tests::run(&a),
        TestModule::Manager(a) => tests::manager_tests::run(&a),
        TestModule::Recording(a) => tests::recording_tests::run(&a),
        TestModule::Pause(a) => tests::pause_tests::run(&a),
        TestModule::Api => {
            let rt = tokio::runtime::Builder::new_multi_thread()
                .worker_threads(4)
                .enable_all()
                .build()?;
            rt.block_on(tests::api_server_tests::run())
        }
        TestModule::Rotate(a) => tests::rotation_tests::run(&a),
        TestModule::Update { module } => dispatch_update(module),
    }
}

fn dispatch_update(module: cli::UpdateModule) -> anyhow::Result<()> {
    use cli::UpdateModule;
    match module {
        UpdateModule::Exposure(a) => tests::update_config_tests::run_exposure_test(&a),
        UpdateModule::AutoExposure(a) => tests::update_config_tests::run_auto_exposure_test(&a),
        UpdateModule::Resolution(a) => tests::update_config_tests::run_resolution_test(&a),
        UpdateModule::Framerate(a) => tests::update_config_tests::run_framerate_test(&a),
        UpdateModule::AddCamera(a) => tests::update_config_tests::run_add_camera_test(&a),
        UpdateModule::RemoveCamera(a) => tests::update_config_tests::run_remove_camera_test(&a),
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
