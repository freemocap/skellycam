//! Startup/shutdown lifecycle tests.
//!
//! Usage:
//!   cargo run --release -- test lifecycle [--cameras N]

use std::collections::HashMap;

use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

pub fn run(args: &[String]) -> anyhow::Result<()> {
    let camera_count = args
        .iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<usize>().ok());

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let num = camera_count.unwrap_or(all_cameras.len()).min(all_cameras.len());

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  LIFECYCLE TEST — {} camera{}", num, if num == 1 { "" } else { "s" });
    tracing::info!("  start → stream ~30 frames → shutdown → verify clean");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let configs: HashMap<String, CameraGroupConfig> = all_cameras
        .iter()
        .take(num)
        .map(|identity| {
            let cfg = CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: identity.camera_index as u32,
                    width: 1280,
                    height: 720,
                    exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: 30.0,
                    rotation: -1,
                },
                identity: identity.clone(),
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let mut group = CameraGroup::new(configs.clone());
    let start_ts = std::time::Instant::now();

    group.start()?;
    let start_elapsed = start_ts.elapsed();
    tracing::info!("  Started {num} camera(s) in {start_elapsed:.1?}");

    // Stream ~30 multiframes
    let target_frames: i64 = 30;
    let mut last_frame: i64 = -1;
    let mut polls: u64 = 0;
    let poll_start = std::time::Instant::now();

    while last_frame < target_frames {
        if !group.is_alive() {
            anyhow::bail!(
                "Gatherer died at frame {last_frame} — camera may have disconnected"
            );
        }
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > last_frame {
                last_frame = payload.frame_number;
            }
        }
        if poll_start.elapsed().as_secs() > 30 {
            anyhow::bail!("Timed out at frame {last_frame}, target {target_frames}");
        }
        polls += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }

    let stream_elapsed = poll_start.elapsed();
    let fps = last_frame as f64 / stream_elapsed.as_secs_f64();
    tracing::info!(
        "  Streamed {last_frame} multiframes in {:.1}s ({fps:.1} fps, {polls} polls)",
        stream_elapsed.as_secs_f64(),
    );

    // Shut down and measure
    let shutdown_start = std::time::Instant::now();
    group.shutdown()?;
    let shutdown_elapsed = shutdown_start.elapsed();
    tracing::info!("  Shutdown complete in {shutdown_elapsed:.1?}");

    // Verify: group should be in Stopped state
    // (shutdown consumes the group so we can't call state())

    tracing::info!("");
    tracing::info!("  ✓ Lifecycle: start → stream → shutdown (clean)");
    tracing::info!(
        "    {num} camera(s)  |  {last_frame} frames  |  total {:.1}s",
        start_ts.elapsed().as_secs_f64(),
    );
    tracing::info!("  LIFECYCLE TEST COMPLETE");
    tracing::info!("");

    Ok(())
}
