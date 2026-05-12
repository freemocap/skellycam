//! Phase 1/2: Camera test harness.
//!
//! IMPORTANT: Always use `cargo run --release` for real performance testing.
//! Debug builds are significantly slower — frame rate may drop below 30fps
//! and timing diagnostics will not reflect actual capture performance.
//!
//! Usage:
//!   cargo run --release -- --detect    # enumerate cameras
//!   cargo run --release                # single-camera test (index 0)

use std::hash::{Hash, Hasher};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::time::{Duration, Instant};

use skellycam::camera::{self, enumerate_directshow_cameras, CameraEvent, CameraIdentity};

fn main() -> anyhow::Result<()> {
    if cfg!(debug_assertions) {
        eprintln!(
            "WARNING: Running in debug mode. Use `cargo run --release` for full performance.\n"
        );
    }
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("skellycam=info")),
        )
        .init();

    let args: Vec<String> = std::env::args().collect();

    if args.iter().any(|arg| arg == "--detect") {
        return run_detection();
    }

    run_single_camera()
}

fn run_detection() -> anyhow::Result<()> {
    let cameras = enumerate_directshow_cameras()?;
    if cameras.is_empty() {
        eprintln!("No cameras found.");
    } else {
        eprintln!(
            "Found {} camera{} total.",
            cameras.len(),
            if cameras.len() == 1 { "" } else { "s" }
        );
    }
    Ok(())
}

fn run_single_camera() -> anyhow::Result<()> {
    let index: u32 = 0;
    let requested_width: u32 = 1280;
    let requested_height: u32 = 720;

    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    format!("Camera {index}").hash(&mut hasher);
    let unique_id = format!("{:016x}", hasher.finish())
        .chars().rev().take(6).collect::<String>()
        .chars().rev().collect::<String>();

    let identity = CameraIdentity {
        display_name: format!("Camera {index}"),
        camera_index: index as i32,
        unique_identifier: unique_id,
        device_path: String::new(),
    };

    println!("Camera {index}: {} at {requested_width}x{requested_height}", identity.label());
    let (handle, event_receiver, frame_receiver) =
        camera::spawn_camera_thread(index, requested_width, requested_height, identity);

    let running = Arc::new(AtomicBool::new(true));
    let running_flag = running.clone();

    // Install CTRL+C handler — sets the flag so the loop can exit cleanly
    let _ = ctrlc::set_handler(move || {
        eprintln!("\nCtrl+C received, shutting down...");
        running_flag.store(false, Ordering::SeqCst);
    });

    let mut start: Option<Instant> = None;
    let mut frame_count: u64 = 0;
    let mut last_report = Instant::now();

    loop {
        if !running.load(Ordering::SeqCst) {
            eprintln!("Shutdown requested, exiting loop.");
            break;
        }

        while let Ok(event) = event_receiver.try_recv() {
            match event {
                CameraEvent::Error(msg) => eprintln!("ERROR: {msg}"),
            }
        }

        // Use recv_timeout so the loop can periodically check the running flag
        // and respond to CTRL+C instead of blocking indefinitely
        match frame_receiver.recv_timeout(Duration::from_millis(100)) {
            Ok(packet) => {
                if start.is_none() {
                    start = Some(Instant::now());
                    last_report = Instant::now();
                }
                frame_count += 1;

                if frame_count <= 3 {
                    println!(
                        "Frame {}: {}x{} ({} KB)",
                        packet.frame_number,
                        packet.width,
                        packet.height,
                        packet.data.len() / 1024,
                    );
                }

                if frame_count % 30 == 0 {
                    let elapsed = last_report.elapsed();
                    let fps = 30.0_f64 / elapsed.as_secs_f64();
                    println!(
                        "Frame {:>5} | {:>5.1} fps | {}x{}",
                        packet.frame_number, fps, packet.width, packet.height,
                    );
                    last_report = Instant::now();
                }

                if frame_count >= 500 {
                    println!("\nReached 500 frames, stopping.");
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                // No frame yet — loop back to check running flag and events
                continue;
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                eprintln!("Camera channel disconnected.");
                break;
            }
        }
    }

    if let Some(s) = start {
        let total = s.elapsed();
        println!(
            "\n{frame_count} frames in {:.1}s ({:.1} fps avg).",
            total.as_secs_f64(),
            frame_count as f64 / total.as_secs_f64(),
        );
    }
    eprintln!("Shutting down camera...");
    drop(handle);
    eprintln!("Done.");
    Ok(())
}
