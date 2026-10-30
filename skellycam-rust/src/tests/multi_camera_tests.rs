use std::collections::HashMap;
use super::info_block;
use std::time::{Duration, Instant};

use crate::cli::MultiArgs;
use skellycam::camera::{detect_cameras, CameraConfig, CameraIdentity};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

pub fn run(args: &MultiArgs) -> anyhow::Result<()> {
    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let indices: Vec<u32> = if let Some(ref explicit) = args.indices {
        explicit.clone()
    } else {
        let count = args.cameras.unwrap_or(all_cameras.len()) as usize;
        all_cameras
            .iter()
            .take(count)
            .map(|c| c.camera_index as u32)
            .collect()
    };
    let max_loops = args.max_loops;

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
                    framerate: -1.0,
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
    let fps_line = if elapsed > 0.0 {
        format!(
            "\n  Multiframe rate:  {:.1} fps",
            (last_frame - 1) as f64 / elapsed
        )
    } else {
        String::new()
    };
    info_block(&[
        &format!(
            "══════════════════════════════════════════════════\n  Multi-Camera Summary\n──────────────────────────────────────────────────\n  Cameras:          {num_cameras}\n  Multiframes:      {last_frame}\n  Capture:          {elapsed:.1}s{fps_line}\n══════════════════════════════════════════════════",
        ),
        "",
    ]);

    tracing::info!("Shutting down...");
    group.shutdown()?;
    tracing::info!("Done.");
    Ok(())
}
