use std::time::{Duration, Instant};

use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::CameraGroupConfig;
use skellycam::camera_group_manager::CameraGroupManager;

pub fn run(args: &[String]) -> anyhow::Result<()> {
    let camera_count = args
        .iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok());

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let camera_count = match camera_count {
        Some(n) => {
            if n as usize > all_cameras.len() {
                anyhow::bail!(
                    "Requested {} cameras but only {} available",
                    n,
                    all_cameras.len()
                );
            }
            n as usize
        }
        None => all_cameras.len(),
    };

    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!(
        "  CAMERA GROUP MANAGER TEST — {} camera{}",
        camera_count,
        if camera_count == 1 { "" } else { "s" }
    );
    tracing::info!("══════════════════════════════════════════════════\n");

    let mut manager = CameraGroupManager::new();

    let configs: Vec<CameraGroupConfig> = all_cameras
        .iter()
        .take(camera_count)
        .map(|identity| CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: 1280,
                height: 720,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: -1.0,
                rotation: -1,
            },
            identity: identity.clone(),
        })
        .collect();

    let group_id = manager.create_or_update_group(configs, None)?;
    tracing::info!("  Created group: {group_id}");
    tracing::info!("  Active groups: {:?}", manager.list_groups());
    tracing::info!("  Group count: {}\n", manager.group_count());

    let state = manager.to_state_dict();
    let state_json = serde_json::to_string_pretty(&state)?;
    tracing::info!("  ── Manager State ──\n{state_json}\n");

    let start = Instant::now();
    let run_duration = Duration::from_secs(5);

    tracing::info!("  Running for {} seconds...\n", run_duration.as_secs());
    while start.elapsed() < run_duration {
        std::thread::sleep(Duration::from_millis(10));
    }
    let frame_count = (start.elapsed().as_millis() / 10) as u64;

    tracing::info!("  ── Results ──");
    tracing::info!("  Polls: {frame_count}");
    tracing::info!("  Cameras in group: {camera_count}");

    manager.close_group(&group_id)?;
    tracing::info!("  Shutdown complete.");
    tracing::info!("══════════════════════════════════════════════════\n");
    Ok(())
}
