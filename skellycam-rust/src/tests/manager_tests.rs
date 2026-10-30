use std::time::{Duration, Instant};

use super::info_block;
use crate::cli::CameraCountArgs;
use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::CameraGroupConfig;
use skellycam::camera_group_manager::CameraGroupManager;

pub fn run(args: &CameraCountArgs) -> anyhow::Result<()> {
    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let camera_count = match args.cameras {
        Some(n) => {
            if n > all_cameras.len() {
                anyhow::bail!(
                    "Requested {} cameras but only {} available",
                    n,
                    all_cameras.len()
                );
            }
            n
        }
        None => all_cameras.len(),
    };

    info_block(&[
        &format!(
            "══════════════════════════════════════════════════\n  CAMERA GROUP MANAGER TEST — {} camera{}\n══════════════════════════════════════════════════",
            camera_count,
            if camera_count == 1 { "" } else { "s" },
        ),
        "",
    ]);

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
    info_block(&[
        &format!(
            "  Created group: {group_id}\n  Active groups: {:?}\n  Group count: {}",
            manager.list_groups(),
            manager.group_count(),
        ),
        "",
    ]);

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

    tracing::info!(
        "\n  ── Results ──\n  Polls: {frame_count}\n  Cameras in group: {camera_count}"
    );

    manager.close_group(&group_id)?;
    tracing::info!("  Shutdown complete.\n══════════════════════════════════════════════════\n");
    Ok(())
}
