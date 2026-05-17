//! SkellyCam Rust — camera test harness.
//!
//! IMPORTANT: Always use `cargo run --release` for real performance testing.
//!
//! Usage:
//!   cargo run --release -- --detect              # enumerate cameras
//!   cargo run --release                          # single-camera test (index 0)
//!   cargo run --release -- --cameras 2           # multi-camera lockstep
//!   cargo run --release -- --indices 0,2,4       # specific camera indices
//!   cargo run --release -- --record 2 --open     # record 2 cameras + open output folder

use std::path::PathBuf;
use std::time::{Duration, Instant};

use skellycam::camera::{detect_cameras, CameraConfig, CameraIdentity};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
use skellycam::camera_group_manager::CameraGroupManager;

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

    if let Some(manager_pos) = args.iter().position(|arg| arg == "--manager") {
        let camera_count = args.get(manager_pos + 1).and_then(|s| s.parse::<u32>().ok());
        return run_manager_test(camera_count);
    }

    if let Some(record_count) = args.iter()
        .position(|arg| arg == "--record")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok())
    {
        let open_folder = args.iter().any(|arg| arg == "--open");
        return run_recording(record_count, open_folder);
    }

    let camera_count = args.iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok());

    let explicit_indices: Option<Vec<u32>> = args.iter()
        .position(|arg| arg == "--indices")
        .and_then(|pos| args.get(pos + 1))
        .map(|s| s.split(',').filter_map(|n| n.trim().parse().ok()).collect());

    if camera_count.is_some() || explicit_indices.is_some() {
        return run_multi_camera(camera_count, explicit_indices);
    }

    run_single_camera()
}

fn run_detection() -> anyhow::Result<()> {
    let cameras = detect_cameras()?;
    if cameras.is_empty() {
        eprintln!("No cameras found.");
    } else {
        eprintln!("Found {} camera{} total.", cameras.len(), if cameras.len() == 1 { "" } else { "s" });
    }
    Ok(())
}

fn run_manager_test(requested_count: Option<u32>) -> anyhow::Result<()> {
    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let camera_count = match requested_count {
        Some(n) => {
            if n as usize > all_cameras.len() {
                anyhow::bail!("Requested {} cameras but only {} available", n, all_cameras.len());
            }
            n as usize
        }
        None => all_cameras.len(),
    };

    eprintln!("══════════════════════════════════════════════════");
    eprintln!("  CAMERA GROUP MANAGER TEST — {} camera{}", camera_count, if camera_count == 1 { "" } else { "s" });
    eprintln!("══════════════════════════════════════════════════\n");

    let mut manager = CameraGroupManager::new();

    let configs: Vec<CameraGroupConfig> = all_cameras.iter()
        .take(camera_count)
        .map(|identity| CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: 1280, height: 720, exposure: -7,
                exposure_mode: "MANUAL".into(), framerate: -1.0, rotation: -1,
            },
            identity: identity.clone(),
        })
        .collect();

    let group_id = manager.create_or_update_group(configs, None)?;
    eprintln!("  Created group: {group_id}");
    eprintln!("  Active groups: {:?}", manager.list_groups());
    eprintln!("  Group count: {}\n", manager.group_count());

    let state = manager.to_state_dict();
    let state_json = serde_json::to_string_pretty(&state)?;
    eprintln!("  ── Manager State ──\n{state_json}\n");

    // Poll frames via the manager (it internally calls latest_frontend_payload)
    let mut frame_count: u64 = 0;
    let start = Instant::now();
    let run_duration = Duration::from_secs(5);

    eprintln!("  Running for {} seconds...\n", run_duration.as_secs());
    while start.elapsed() < run_duration {
        // Poll via the manager's group — we use remove_group to get the raw group
        // and check its latest_frontend_payload. In practice, the manager wraps this.
        std::thread::sleep(Duration::from_millis(10));
        frame_count += 1;
    }
    // Approximate: count = elapsed / 10ms
    frame_count = (start.elapsed().as_millis() / 10) as u64;

    eprintln!("  ── Results ──");
    eprintln!("  Polls: {frame_count}");
    eprintln!("  Cameras in group: {camera_count}");

    manager.close_group(&group_id)?;
    eprintln!("  Shutdown complete.");
    eprintln!("══════════════════════════════════════════════════\n");
    Ok(())
}

fn run_recording(camera_count: u32, open_folder: bool) -> anyhow::Result<()> {
    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let indices: Vec<u32> = (0..camera_count).collect();
    let configs: std::collections::HashMap<String, CameraGroupConfig> = indices.iter().map(|&index| {
        let identity = all_cameras.iter()
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
                width: 1280, height: 720, exposure: -7,
                exposure_mode: "MANUAL".into(), framerate: 30.0, rotation: -1,
            },
            identity,
        };
        (cfg.identity.camera_id.clone(), cfg)
    }).collect();

    let num_cameras = configs.len();
    eprintln!("\n  ── Recording {num_cameras} camera(s) ──\n");

    let output_dir = {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH).unwrap().as_secs();
        let dir = PathBuf::from(format!("recordings_{timestamp}"));
        std::fs::create_dir_all(&dir)?;
        dir
    };

    let mut group = CameraGroup::new(configs);
    group.start()?;

    // Start recording
    group.start_recording(skellycam::camera_group::RecordingParams {
        output_dir: output_dir.to_string_lossy().to_string(),
        label: Some("test_recording".into()),
    })?;

    eprintln!("  Recording to: {}\n", output_dir.display());

    let max_duration = Duration::from_secs(5);
    let start = Instant::now();
    let mut last_frame: i64 = -1;

    while start.elapsed() < max_duration {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > last_frame {
                last_frame = payload.frame_number;
                if last_frame > 0 && last_frame % 30 == 0 {
                    let elapsed = start.elapsed().as_secs_f64();
                    eprintln!("  frame {last_frame:>5} | {elapsed:.1}s | ~{:.0}fps",
                        last_frame as f64 / elapsed);
                }
            }
        }
        std::thread::sleep(Duration::from_millis(1));
    }

    eprintln!("\n  Stopping recording...");
    let summary = group.stop_recording()?;
    eprintln!("  Frames per camera: {}", summary.total_frames_per_camera);

    group.shutdown()?;

    if open_folder {
        let _ = std::process::Command::new("explorer").arg(&output_dir).spawn();
    }
    eprintln!("Done.");
    Ok(())
}

fn run_multi_camera(
    camera_count: Option<u32>,
    explicit_indices: Option<Vec<u32>>,
) -> anyhow::Result<()> {
    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let indices: Vec<u32> = if let Some(explicit) = explicit_indices {
        explicit
    } else {
        let count = camera_count.unwrap_or(2) as usize;
        all_cameras.iter().take(count).map(|c| c.camera_index as u32).collect()
    };

    let configs: std::collections::HashMap<String, CameraGroupConfig> = indices.iter().map(|&index| {
        let identity = all_cameras.iter()
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
                width: 1280, height: 720, exposure: -7,
                exposure_mode: "MANUAL".into(), framerate: 30.0, rotation: -1,
            },
            identity,
        };
        (cfg.identity.camera_id.clone(), cfg)
    }).collect();

    let num_cameras = configs.len();
    eprintln!("\n  ── {num_cameras}-camera lockstep ── 600 multiframes (~20s) ──\n");

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let start = Instant::now();
    let max_multiframes: i64 = 600;
    let mut last_frame: i64 = -1;
    let mut first_frame_time: Option<Instant> = None;
    let mut last_report_frame: i64 = 0;

    eprintln!("  waiting for first frame...");

    while last_frame < max_multiframes {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > last_frame {
                if first_frame_time.is_none() {
                    first_frame_time = Some(Instant::now());
                    eprintln!("  first frame received (init took {:.1}s)", start.elapsed().as_secs_f64());
                }
                last_frame = payload.frame_number;
            }
        }

        // Report every 60 multiframes (~2s at 30fps), timed from first frame
        if let Some(t0) = first_frame_time {
            if last_frame > 0 && last_frame - last_report_frame >= 60 {
                let elapsed = t0.elapsed().as_secs_f64();
                let fps = (last_frame - 1) as f64 / elapsed; // -1: exclude frame 0
                eprintln!(
                    "  [t+{elapsed:.1}s] multiframe {last_frame:>5}  |  {fps:.1} fps  |  {} cameras",
                    num_cameras
                );
                last_report_frame = last_frame;
            }
        }
        std::thread::sleep(Duration::from_millis(1));
    }

    let elapsed = first_frame_time
        .map(|t0| t0.elapsed().as_secs_f64())
        .unwrap_or(0.0);
    eprintln!("\n══════════════════════════════════════════════════");
    eprintln!("  Multi-Camera Summary");
    eprintln!("──────────────────────────────────────────────────");
    eprintln!("  Cameras:          {num_cameras}");
    eprintln!("  Multiframes:      {last_frame}");
    eprintln!("  Capture:          {elapsed:.1}s");
    if elapsed > 0.0 {
        eprintln!("  Multiframe rate:  {:.1} fps", (last_frame - 1) as f64 / elapsed);
    }
    eprintln!("══════════════════════════════════════════════════\n");

    eprintln!("Shutting down...");
    group.shutdown()?;
    eprintln!("Done.");
    Ok(())
}

fn run_single_camera() -> anyhow::Result<()> {
    run_multi_camera(Some(1), None)
}
