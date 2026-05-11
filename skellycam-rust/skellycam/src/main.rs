//! SkellyCam — nokhwa MJPEG passthrough, single camera test.

use std::hash::{Hash, Hasher};
use std::sync::mpsc;
use std::time::Instant;

use tracing_subscriber::EnvFilter;

use skellycam::camera::{self, CameraEvent, CameraIdentity};
use skellycam::camera_group;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("skellycam=info")),
        )
        .init();

    tracing::info!("SkellyCam starting (nokhwa MJPEG passthrough)...");

    // Probe for cameras
    let cameras = nokhwa::query(nokhwa::utils::ApiBackend::Auto)
        .map_err(|error| anyhow::anyhow!("Failed to query cameras: {error}"))?;

    if cameras.is_empty() {
        anyhow::bail!("No cameras found.");
    }

    println!("Found {} camera(s):", cameras.len());
    for (i, info) in cameras.iter().enumerate() {
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        info.misc().hash(&mut hasher);
        let unique_id = format!("{:016x}", hasher.finish())
            .chars().rev().take(6).collect::<String>()
            .chars().rev().collect::<String>();
        println!("  Camera {i}: {} [{unique_id}]  ({})", info.human_name(), info.misc());
    }
    println!();

    // Skip camera 4 (Logitech C310) — frame() blocks at 720p
    let camera_indices: Vec<u32> = (0..cameras.len() as u32).filter(|&i| i != 4).collect();
    let number_of_cameras = camera_indices.len();
    let requested_width: u32 = 1280;
    let requested_height: u32 = 720;

    // Spawn all cameras
    let mut handles = Vec::new();
    let mut event_receivers = Vec::new();
    let mut frame_receivers = Vec::new();

    for &index in &camera_indices {
        let camera_info = &cameras[index as usize];

        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        camera_info.misc().hash(&mut hasher);
        let unique_id = format!("{:016x}", hasher.finish())
            .chars().rev().take(6).collect::<String>()
            .chars().rev().collect::<String>();

        let identity = CameraIdentity {
            display_name: camera_info.human_name(),
            camera_index: index as i32,
            unique_identifier: unique_id,
            device_path: camera_info.misc(),
        };

        tracing::info!("Starting camera {index} ({})...", identity.label());

        let (handle, event_rx, frame_rx) = camera::spawn_camera_thread(
            index,
            requested_width,
            requested_height,
            identity,
        );

        handles.push(handle);
        event_receivers.push(event_rx);
        frame_receivers.push(frame_rx);
    }

    // Spawn gatherer
    let multiframe_receiver = camera_group::spawn_gatherer(frame_receivers);

    println!(
        "Streaming {number_of_cameras} camera(s) at {requested_width}x{requested_height}. Ctrl+C to stop.\n"
    );

    let start = Instant::now();
    let mut multiframe_count: u64 = 0;
    let mut last_report = Instant::now();

    let receive_handle = tokio::task::spawn_blocking(move || -> anyhow::Result<()> {
        loop {
            for event_rx in &event_receivers {
                while let Ok(event) = event_rx.try_recv() {
                    match event {
                        CameraEvent::Error(message) => {
                            eprintln!("ERROR: {message}");
                        }
                    }
                }
            }

            match multiframe_receiver.recv() {
                Ok(payload) => {
                    multiframe_count += 1;

                    let frame_numbers: Vec<i64> = payload
                        .frames.iter().map(|f| f.frame_number).collect();
                    let first = frame_numbers[0];
                    let all_match = frame_numbers.iter().all(|&n| n == first);

                    if !all_match {
                        eprintln!(
                            "LOCKSTEP VIOLATION at step {}: {:?}",
                            payload.step, frame_numbers
                        );
                    }

                    let spread_ns = payload.inter_camera_grab_spread_nanoseconds();

                    if multiframe_count % 60 == 0 {
                        let elapsed = last_report.elapsed();
                        let fps = 60.0 / elapsed.as_secs_f64();

                        let sizes: Vec<String> = payload
                            .frames
                            .iter()
                            .map(|f| format!("{}×{} {}KB", f.width, f.height, f.jpeg_bytes.len() / 1024))
                            .collect();

                        println!(
                            "Step {:>5} | {:>5.1} fps | sync {:>6.0} µs | {} cams | {}",
                            payload.step,
                            fps,
                            spread_ns as f64 / 1_000.0,
                            payload.frames.len(),
                            sizes.join(", "),
                        );

                        last_report = Instant::now();
                    }
                }
                Err(mpsc::RecvError) => {
                    tracing::info!("Gatherer disconnected.");
                    break;
                }
            }
        }

        let total = start.elapsed();
        println!(
            "\nStream ended. {} multiframes in {:.1}s ({:.1} fps avg).",
            multiframe_count,
            total.as_secs_f64(),
            multiframe_count as f64 / total.as_secs_f64(),
        );
        Ok(())
    });

    tokio::signal::ctrl_c().await?;
    tracing::info!("Shutting down...");
    drop(handles);

    let _ = tokio::time::timeout(std::time::Duration::from_secs(3), receive_handle).await;
    tracing::info!("Done.");
    Ok(())
}
