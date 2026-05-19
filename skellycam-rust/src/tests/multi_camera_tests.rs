use std::collections::HashMap;
use std::time::{Duration, Instant};

use skellycam::camera::{detect_cameras, CameraConfig, CameraIdentity};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

pub fn run(args: &[String]) -> anyhow::Result<()> {
    let camera_count = args
        .iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok());

    let explicit_indices: Option<Vec<u32>> = args
        .iter()
        .position(|arg| arg == "--indices")
        .and_then(|pos| args.get(pos + 1))
        .map(|s| s.split(',').filter_map(|n| n.trim().parse().ok()).collect());

    let max_loops: i64 = args
        .iter()
        .position(|arg| arg == "--max-loops")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse().ok())
        .unwrap_or(-1);

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let indices: Vec<u32> = if let Some(explicit) = explicit_indices {
        explicit
    } else {
        let count = camera_count.unwrap_or(2) as usize;
        all_cameras
            .iter()
            .take(count)
            .map(|c| c.camera_index as u32)
            .collect()
    };

    let configs: HashMap<String, CameraGroupConfig> = indices
        .iter()
        .map(|&index| {
            let identity = all_cameras
                .iter()
                .find(|c| c.camera_index == index as i32)
                .cloned()
                .unwrap_or_else(|| CameraIdentity {
                    camera_name: format!("Camera {index}"),
                    camera_index: index as i32,
                    camera_id: format!("{:06x}", index),
                    device_path: String::new(),
                    formats: vec![],
                });
            let cfg = CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: index,
                    width: 1280,
                    height: 720,
                    exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: 30.0,
                    rotation: -1,
                },
                identity,
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let num_cameras = configs.len();
    if max_loops < 0 {
        tracing::info!("\n  ── {num_cameras}-camera lockstep ── running indefinitely ──\n");
    } else {
        tracing::info!("\n  ── {num_cameras}-camera lockstep ── {max_loops} multiframes ──\n");
    }

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let start = Instant::now();
    let mut last_frame: i64 = -1;
    let mut first_frame_time: Option<Instant> = None;
    let mut last_report_frame: i64 = 0;

    tracing::info!("  waiting for first frame...");

    while max_loops < 0 || last_frame < max_loops {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > last_frame {
                if first_frame_time.is_none() {
                    first_frame_time = Some(Instant::now());
                    tracing::info!(
                        "  first frame received (init took {:.1}s)",
                        start.elapsed().as_secs_f64()
                    );
                }
                last_frame = payload.frame_number;
            }
        }

        if let Some(t0) = first_frame_time {
            if last_frame > 0 && last_frame - last_report_frame >= 60 {
                let elapsed = t0.elapsed().as_secs_f64();
                let fps = (last_frame - 1) as f64 / elapsed;
                tracing::debug!(
                    "  [t+{elapsed:.1}s] multiframe {last_frame:>5}  |  {fps:.1} fps  |  {} cameras",
                    num_cameras
                );
                last_report_frame = last_frame;
            }
        }
        if !group.is_alive() {
            anyhow::bail!(
                "Gatherer died at frame {last_frame} (target {max_loops}) — camera may have disconnected"
            );
        }
        std::thread::sleep(Duration::from_millis(1));
    }

    let elapsed = first_frame_time
        .map(|t0| t0.elapsed().as_secs_f64())
        .unwrap_or(0.0);
    tracing::info!("\n══════════════════════════════════════════════════");
    tracing::info!("  Multi-Camera Summary");
    tracing::info!("──────────────────────────────────────────────────");
    tracing::info!("  Cameras:          {num_cameras}");
    tracing::info!("  Multiframes:      {last_frame}");
    tracing::info!("  Capture:          {elapsed:.1}s");
    if elapsed > 0.0 {
        tracing::info!(
            "  Multiframe rate:  {:.1} fps",
            (last_frame - 1) as f64 / elapsed
        );
    }
    tracing::info!("══════════════════════════════════════════════════\n");

    tracing::info!("Shutting down...");
    group.shutdown()?;
    tracing::info!("Done.");
    Ok(())
}
