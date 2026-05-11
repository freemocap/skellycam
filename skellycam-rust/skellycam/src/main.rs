//! Phase 1: Single camera test — verify 30fps at 1280x720.

use std::hash::{Hash, Hasher};
use std::sync::mpsc;
use std::time::Instant;

use skellycam::camera::{self, CameraEvent, CameraIdentity};

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("skellycam=info")),
        )
        .init();

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

    let start = Instant::now();
    let mut frame_count: u64 = 0;
    let mut last_report = Instant::now();

    loop {
        while let Ok(event) = event_receiver.try_recv() {
            match event {
                CameraEvent::Error(msg) => eprintln!("ERROR: {msg}"),
            }
        }

        match frame_receiver.recv() {
            Ok(packet) => {
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

                if frame_count % 60 == 0 {
                    let elapsed = last_report.elapsed();
                    let fps = 60.0 / elapsed.as_secs_f64();
                    println!(
                        "Frame {:>5} | {:>5.1} fps | {}x{}",
                        packet.frame_number, fps, packet.width, packet.height,
                    );
                    last_report = Instant::now();
                }
            }
            Err(mpsc::RecvError) => break,
        }
    }

    let total = start.elapsed();
    println!(
        "\n{frame_count} frames in {:.1}s ({:.1} fps avg).",
        total.as_secs_f64(),
        frame_count as f64 / total.as_secs_f64(),
    );
    drop(handle);
    Ok(())
}
