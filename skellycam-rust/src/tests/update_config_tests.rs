//! Update-config integration tests.
//!
//! Subcommand routing:
//!   test update exposure [--cameras N]       — change exposure, verify image brightness
//!   test update resolution [--camera-index I] — change resolution (if multiple formats)
//!   test update framerate [--camera-index I] — change framerate (if multiple formats)
//!   test update add-camera [--cameras N]      — add a camera mid-stream
//!   test update remove-camera [--cameras N]   — remove a camera mid-stream

use crate::cli::{CameraCountArgs, ResolutionArgs, FramerateArgs};
use skellycam::camera_group::CameraGroup;

// ── Exposure test ──────────────────────────────────────────────────────────────

pub fn run_exposure_test(args: &CameraCountArgs) -> anyhow::Result<()> {
    use std::collections::HashMap;
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let num = args.cameras.unwrap_or(all_cameras.len());

    // The camera reports its hardware exposure range during stream open.
    // We detect it from the logs (min=-13 max=-1 default=-6 for these USB cams).
    // We scan the full reported range plus a couple values outside it to see
    // if the driver clamps, ignores, or errors on out-of-range requests.
    let reported_range: Vec<i32> = (-13..=-1).collect();
    let outside_range: Vec<i32> = vec![-15, 0];
    let mut test_values: Vec<i32> = reported_range.clone();
    test_values.extend(&outside_range);
    // Sort so we sweep from darkest (lowest number) to brightest
    test_values.sort();

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  EXPOSURE RANGE SCAN — {} camera{}", num, if num == 1 { "" } else { "s" });
    tracing::info!("  Reported range: {}..=-1", reported_range.first().unwrap());
    tracing::info!("  Testing: {} values (reported range + outside-range probes)", test_values.len());
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
                    width: 1280, height: 720,
                    exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: -1.0, rotation: -1,
                },
                identity: identity.clone(),
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut polls, 30)?;

    // ── Scan each exposure value ──────────────────────────────────────────
    let mut prev_lum: Option<f64> = None;

    for &exposure_value in &test_values {
        let in_range = reported_range.contains(&exposure_value);
        let label = if in_range { "" } else { " [OUTSIDE REPORTED RANGE]" };

        let mut new_configs: HashMap<String, CameraGroupConfig> = HashMap::new();
        for status in group.camera_statuses() {
            let mut new_cfg = status.config.clone();
            new_cfg.exposure = exposure_value;
            new_configs.insert(
                status.config.camera_id.clone(),
                CameraGroupConfig {
                    capture_config: new_cfg,
                    identity: all_cameras.iter()
                        .find(|c| c.camera_index == status.camera_index)
                        .cloned()
                        .unwrap_or_else(|| skellycam::camera::CameraIdentity {
                            camera_name: status.camera_name.clone(),
                            camera_index: status.camera_index,
                            camera_id: status.config.camera_id.clone(),
                            device_path: status.device_path.clone(),
                            formats: vec![],
                        }),
                },
            );
        }
        group.apply(new_configs)?;
        std::thread::sleep(std::time::Duration::from_millis(300));

        let target = current_frame + 15;
        poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

        let luminance = capture_brightness_sample(&group);

        // Show direction from previous value
        let direction = if let Some(prev) = prev_lum {
            if luminance > prev * 1.02 { "↑" }
            else if luminance < prev * 0.98 { "↓" }
            else { "→" }
        } else { "—" };

        // Verify camera_statuses reflect the applied value
        let statuses_ok = group.camera_statuses().iter()
            .all(|s| s.config.exposure == exposure_value);

        tracing::info!(
            "  exp={:>4} {} lum={:.1} {} status_ok={}",
            exposure_value, label, luminance, direction, statuses_ok,
        );

        prev_lum = Some(luminance);
    }

    tracing::info!("");

    group.shutdown()?;
    tracing::info!("  EXPOSURE RANGE SCAN COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Auto-Exposure test ────────────────────────────────────────────────────────

pub fn run_auto_exposure_test(args: &CameraCountArgs) -> anyhow::Result<()> {
    use std::collections::HashMap;
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let num = args.cameras.unwrap_or(all_cameras.len());

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  AUTO-EXPOSURE TEST — {} camera{}", num, if num == 1 { "" } else { "s" });
    tracing::info!("  MANUAL dark → AUTO (should brighten) → MANUAL bright → AUTO (should darken)");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let configs: HashMap<String, CameraGroupConfig> = all_cameras
        .iter()
        .take(num as usize)
        .map(|identity| {
            let cfg = CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: identity.camera_index as u32,
                    width: 1280, height: 720,
                    exposure: -11,
                    exposure_mode: "MANUAL".into(),
                    framerate: -1.0, rotation: -1,
                },
                identity: identity.clone(),
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut polls, 30)?;

    // ── Phase 1: MANUAL dark (-11) → AUTO (should brighten) ──────────────
    tracing::info!("  ── Phase 1: AUTO recovery from dark ──");

    // Confirm dark
    let dark_lum = capture_brightness_sample(&group);
    tracing::info!("  MANUAL exposure=-11 → luminance={dark_lum:.2} (dark)");

    // Switch to AUTO
    apply_exposure_mode(&mut group, &all_cameras, "AUTO", -11);
    let target = current_frame + 20;
    poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

    let auto_from_dark = capture_brightness_sample(&group);
    let brightened = auto_from_dark > dark_lum * 1.10;
    let ratio = auto_from_dark / dark_lum.max(0.01);
    tracing::info!("  AUTO (from dark) → luminance={auto_from_dark:.2} ({ratio:.1}x)  {}",
        if brightened { "✓ brightened" } else { "? didn't brighten significantly" });

    // ── Phase 2: MANUAL bright (-3) → AUTO (should darken) ───────────────
    tracing::info!("  ── Phase 2: AUTO recovery from bright ──");

    apply_exposure_mode(&mut group, &all_cameras, "MANUAL", -3);
    let target = current_frame + 20;
    poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

    let bright_lum = capture_brightness_sample(&group);
    tracing::info!("  MANUAL exposure=-3 → luminance={bright_lum:.2} (bright/saturated)");

    apply_exposure_mode(&mut group, &all_cameras, "AUTO", -3);
    let target = current_frame + 20;
    poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

    let auto_from_bright = capture_brightness_sample(&group);
    let darkened = auto_from_bright < bright_lum * 0.90;
    let ratio = bright_lum / auto_from_bright.max(0.01);
    tracing::info!("  AUTO (from bright) → luminance={auto_from_bright:.2} (1/{ratio:.1}x)  {}",
        if darkened { "✓ darkened" } else { "? didn't darken significantly" });

    // ── Summary ───────────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Summary ──");
    tracing::info!("  dark MANUAL={dark_lum:.2} → AUTO={auto_from_dark:.2} (target: brighten)");
    tracing::info!("  bright MANUAL={bright_lum:.2} → AUTO={auto_from_bright:.2} (target: darken)");

    if auto_from_dark < 1.0 && auto_from_bright < 1.0 {
        tracing::warn!("  ? AUTO barely changed from either extreme — camera may not support auto-exposure");
    } else if brightened && darkened {
        tracing::info!("  ✓ AUTO successfully corrects in both directions");
    }

    group.shutdown()?;
    tracing::info!("  AUTO-EXPOSURE TEST COMPLETE");
    tracing::info!("");

    Ok(())
}

/// Apply a new exposure mode and value to all cameras in the group.
fn apply_exposure_mode(
    group: &mut CameraGroup,
    all_cameras: &[skellycam::camera::CameraIdentity],
    mode: &str,
    exposure: i32,
) {
    use std::collections::HashMap;
    use skellycam::camera_group::CameraGroupConfig;
    let mut new_configs = HashMap::new();
    for status in group.camera_statuses() {
        let mut new_cfg = status.config.clone();
        new_cfg.exposure_mode = mode.to_string();
        new_cfg.exposure = exposure;
        new_configs.insert(
            status.config.camera_id.clone(),
            CameraGroupConfig {
                capture_config: new_cfg,
                identity: all_cameras.iter()
                    .find(|c| c.camera_index == status.camera_index)
                    .cloned()
                    .expect("camera identity not found"),
            },
        );
    }
    group.apply(new_configs).expect("apply exposure mode");
    std::thread::sleep(std::time::Duration::from_millis(500));
}

// ── Resolution test ────────────────────────────────────────────────────────────

pub fn run_resolution_test(args: &ResolutionArgs) -> anyhow::Result<()> {
    use std::collections::BTreeSet;
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let identity = all_cameras
        .iter()
        .find(|c| c.camera_index == args.camera_index as i32)
        .ok_or_else(|| anyhow::anyhow!("Camera index {} not found", args.camera_index))?;

    // Collect all unique MJPG resolutions (deduplicated, sorted by pixel count)
    let unique_resolutions: BTreeSet<(u64, u32, u32, u32)> = identity
        .formats
        .iter()
        .filter(|f| f.fourcc_str == "MJPG")
        .map(|f| ((f.width as u64) * (f.height as u64), f.width, f.height, f.fps))
        .collect();

    let mut resolutions: Vec<(u32, u32, u32)> = unique_resolutions
        .into_iter()
        .map(|(_, w, h, fps)| (w, h, fps))
        .collect();

    if resolutions.is_empty() {
        anyhow::bail!("No MJPG formats found");
    }

    // Sample evenly; default to 5. Pass --sample=0 to scan every resolution.
    let sample_n = args.sample;
    if sample_n > 0 && resolutions.len() > sample_n {
        let step = resolutions.len() as f64 / sample_n as f64;
        let mut sampled = Vec::with_capacity(sample_n);
        sampled.push(resolutions[0]);
        for i in 1..(sample_n - 1) {
            let idx = (i as f64 * step).round() as usize;
            sampled.push(resolutions[idx.min(resolutions.len() - 2)]);
        }
        sampled.push(resolutions[resolutions.len() - 1]);
        resolutions = sampled;
    }

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!(
        "  RESOLUTION SCAN — {} ({} of {} resolutions sampled)",
        identity.label(),
        resolutions.len(),
        sample_n,
    );
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    // Start at the lowest resolution
    let first = &resolutions[0];
    let mut configs = HashMap::new();
    configs.insert(
        identity.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: first.0, height: first.1,
                exposure: -7, exposure_mode: "MANUAL".into(),
                framerate: first.2 as f64, rotation: -1,
            },
            identity: identity.clone(),
        },
    );

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut polls, 20)?;

    // Scan each resolution
    for &(width, height, fps) in &resolutions {
        let mut new_configs = HashMap::new();
        new_configs.insert(
            identity.camera_id.clone(),
            CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: identity.camera_index as u32,
                    width, height, exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: fps as f64, rotation: -1,
                },
                identity: identity.clone(),
            },
        );
        group.apply(new_configs)?;
        std::thread::sleep(std::time::Duration::from_millis(300));

        let target = current_frame + 10;
        poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

        // Check config and actual frame dimensions
        let cfg_dims = group.camera_statuses()
            .first()
            .map(|s| format!("{}x{}", s.config.width, s.config.height))
            .unwrap_or_default();

        let actual_dims = group.latest_raw_frames()
            .and_then(|fs| fs.first().map(|f| format!("{}x{}", f.width, f.height)))
            .unwrap_or_else(|| "no frame".to_string());

        let config_match = cfg_dims == format!("{width}x{height}");
        let actual_match = actual_dims == format!("{width}x{height}");

        tracing::info!(
            "  {width}x{height} @{fps}fps  cfg={:5}  actual={}  {}",
            config_match,
            actual_dims,
            if actual_match { "✓" } else { "? stream not restarted" },
        );
    }

    tracing::info!("");

    group.shutdown()?;
    tracing::info!("  RESOLUTION SCAN COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Framerate test ─────────────────────────────────────────────────────────────

pub fn run_framerate_test(args: &FramerateArgs) -> anyhow::Result<()> {
    use std::collections::BTreeSet;
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let identity = all_cameras
        .iter()
        .find(|c| c.camera_index == args.camera_index as i32)
        .ok_or_else(|| anyhow::anyhow!("Camera index {} not found", args.camera_index))?;

    // Collect unique (fps, width, height) combos across ALL MJPG formats,
    // sorted by fps then resolution
    let unique_combos: BTreeSet<(u32, u32, u32)> = identity
        .formats
        .iter()
        .filter(|f| f.fourcc_str == "MJPG")
        .map(|f| (f.fps, f.width, f.height))
        .collect();

    let mut combos: Vec<(u32, u32, u32)> = unique_combos.into_iter().collect();

    if combos.is_empty() {
        anyhow::bail!("No MJPG formats found");
    }

    let unique_fps: Vec<u32> = {
        let fps_set: BTreeSet<u32> = combos.iter().map(|(fps, _, _)| *fps).collect();
        fps_set.into_iter().collect()
    };

    // Sample evenly; default to 5. Pass --sample=0 to scan every combo.
    let sample_n = args.sample;
    let total_combos = combos.len();
    if sample_n > 0 && combos.len() > sample_n {
        let step = combos.len() as f64 / sample_n as f64;
        let mut sampled = Vec::with_capacity(sample_n);
        sampled.push(combos[0]);
        for i in 1..(sample_n - 1) {
            let idx = (i as f64 * step).round() as usize;
            sampled.push(combos[idx.min(combos.len() - 2)]);
        }
        sampled.push(combos[combos.len() - 1]);
        combos = sampled;
    }

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!(
        "  FRAMERATE SCAN — {} ({} unique fps × {} of {} combos sampled)",
        identity.label(),
        unique_fps.len(),
        combos.len(),
        total_combos,
    );
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    // Start at the lowest-fps, lowest-resolution combo
    let first = &combos[0];
    let mut configs = HashMap::new();
    configs.insert(
        identity.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: first.1, height: first.2,
                exposure: -7, exposure_mode: "MANUAL".into(),
                framerate: first.0 as f64, rotation: -1,
            },
            identity: identity.clone(),
        },
    );

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut polls, 20)?;

    // Scan each combo
    for &(fps, width, height) in &combos {
        let mut new_configs = HashMap::new();
        new_configs.insert(
            identity.camera_id.clone(),
            CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: identity.camera_index as u32,
                    width, height, exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: fps as f64, rotation: -1,
                },
                identity: identity.clone(),
            },
        );
        group.apply(new_configs)?;
        std::thread::sleep(std::time::Duration::from_millis(300));

        let target = current_frame + 10;
        poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

        let cfg_fps = group.camera_statuses()
            .first()
            .map(|s| s.config.framerate)
            .unwrap_or(-1.0);

        let actual_dims = group.latest_raw_frames()
            .and_then(|fs| fs.first().map(|f| format!("{}x{}", f.width, f.height)))
            .unwrap_or_else(|| "no frame".to_string());

        let expected_dims = format!("{width}x{height}");
        let dims_match = actual_dims == expected_dims;

        tracing::info!(
            "  {}x{} @{:>2}fps  cfg_fps={:<4.0}  actual={}  {}",
            width, height, fps, cfg_fps, actual_dims,
            if dims_match { "✓" } else { "? stream restarted" },
        );
    }

    tracing::info!("");

    group.shutdown()?;
    tracing::info!("  FRAMERATE SCAN COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Add-camera test ────────────────────────────────────────────────────────────

pub fn run_add_camera_test(args: &CameraCountArgs) -> anyhow::Result<()> {
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    let camera_count = args.cameras.unwrap_or(all_cameras.len()) as u32;
    if camera_count < 2 {
        anyhow::bail!("Need at least 2 cameras for add-camera test (one to start, one to add)");
    }

    if all_cameras.len() < camera_count as usize {
        anyhow::bail!(
            "Requested {camera_count} cameras but only {} available",
            all_cameras.len()
        );
    }

    // Start with N-1 cameras, reserve the Nth for mid-stream addition
    let start_count = (camera_count - 1) as usize;
    let reserved = &all_cameras[start_count]; // camera to add later

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  ADD-CAMERA TEST — start with {start_count}, add '{}'", reserved.label());
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let configs: HashMap<String, CameraGroupConfig> = all_cameras
        .iter()
        .take(start_count)
        .map(|identity| {
            let cfg = CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: identity.camera_index as u32,
                    width: 1280, height: 720, exposure: -7,
                    exposure_mode: "MANUAL".into(), framerate: -1.0, rotation: -1,
                },
                identity: identity.clone(),
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut polls, 30)?;

    let init_count = group.camera_count();
    assert_eq!(init_count, start_count, "should start with {start_count} cameras");
    tracing::info!("  Initial camera count: {init_count}");

    // Add the reserved camera
    let mut new_configs: HashMap<String, CameraGroupConfig> = HashMap::new();
    for status in group.camera_statuses() {
        new_configs.insert(
            status.config.camera_id.clone(),
            CameraGroupConfig {
                capture_config: status.config.clone(),
                identity: all_cameras
                    .iter()
                    .find(|c| c.camera_index == status.camera_index)
                    .cloned()
                    .unwrap(),
            },
        );
    }
    // Add the reserved camera
    new_configs.insert(
        reserved.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: reserved.camera_id.clone(),
                camera_index: reserved.camera_index as u32,
                width: 1280, height: 720, exposure: -7,
                exposure_mode: "MANUAL".into(), framerate: -1.0, rotation: -1,
            },
            identity: reserved.clone(),
        },
    );

    tracing::info!("  Applying config with added camera...");
    group.apply(new_configs)?;

    // Poll to let the new camera join
    let target = current_frame + 60;
    poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

    let new_count = group.camera_count();
    assert_eq!(
        new_count,
        camera_count as usize,
        "should have {camera_count} cameras after add, got {new_count}"
    );
    tracing::info!("  Camera count after add: {new_count}");

    // Verify the new camera shows up in statuses
    let statuses = group.camera_statuses();
    let added_status = statuses
        .iter()
        .find(|s| s.config.camera_id == reserved.camera_id);
    assert!(
        added_status.is_some(),
        "Added camera '{}' not found in camera_statuses()",
        reserved.camera_id
    );
    tracing::info!(
        "  ✓ Camera '{}' present in statuses",
        reserved.label()
    );

    group.shutdown()?;
    tracing::info!("  Shutdown complete.");
    tracing::info!("  ADD-CAMERA TEST COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Remove-camera test ─────────────────────────────────────────────────────────

pub fn run_remove_camera_test(args: &CameraCountArgs) -> anyhow::Result<()> {
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    let camera_count = args.cameras.unwrap_or(all_cameras.len()) as u32;
    if camera_count < 2 {
        anyhow::bail!("Need at least 2 cameras for remove-camera test");
    }

    if all_cameras.len() < camera_count as usize {
        anyhow::bail!(
            "Requested {camera_count} cameras but only {} available",
            all_cameras.len()
        );
    }

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  REMOVE-CAMERA TEST — start with {camera_count}, remove one");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let configs: HashMap<String, CameraGroupConfig> = all_cameras
        .iter()
        .take(camera_count as usize)
        .map(|identity| {
            let cfg = CameraGroupConfig {
                capture_config: CameraConfig {
                    camera_id: identity.camera_id.clone(),
                    camera_index: identity.camera_index as u32,
                    width: 1280, height: 720, exposure: -7,
                    exposure_mode: "MANUAL".into(), framerate: -1.0, rotation: -1,
                },
                identity: identity.clone(),
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let camera_to_remove = all_cameras[camera_count as usize - 1].camera_id.clone();

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut polls, 30)?;

    let init_count = group.camera_count();
    tracing::info!("  Initial camera count: {init_count}");

    // Remove the last camera
    let mut new_configs: HashMap<String, CameraGroupConfig> = HashMap::new();
    for status in group.camera_statuses() {
        if status.config.camera_id == camera_to_remove {
            continue; // skip this one
        }
        new_configs.insert(
            status.config.camera_id.clone(),
            CameraGroupConfig {
                capture_config: status.config.clone(),
                identity: all_cameras
                    .iter()
                    .find(|c| c.camera_index == status.camera_index)
                    .cloned()
                    .unwrap(),
            },
        );
    }

    tracing::info!("  Applying config without camera '{camera_to_remove}'...");
    group.apply(new_configs)?;

    let target = current_frame + 30;
    poll_frames(&mut group, &mut current_frame, &mut polls, target)?;

    let new_count = group.camera_count();
    assert_eq!(
        new_count,
        (camera_count - 1) as usize,
        "should have {} cameras after remove, got {new_count}",
        camera_count - 1,
    );
    tracing::info!("  Camera count after remove: {new_count}");

    // Verify removed camera is gone from statuses
    let statuses = group.camera_statuses();
    let removed_status = statuses
        .iter()
        .find(|s| s.config.camera_id == camera_to_remove);
    assert!(
        removed_status.is_none(),
        "Removed camera '{camera_to_remove}' still present in camera_statuses()"
    );
    tracing::info!("  ✓ Camera '{camera_to_remove}' removed from statuses");

    group.shutdown()?;
    tracing::info!("  Shutdown complete.");
    tracing::info!("  REMOVE-CAMERA TEST COMPLETE");
    tracing::info!("");

    Ok(())
}

fn poll_frames(
    group: &CameraGroup,
    current_frame: &mut i64,
    polls: &mut u64,
    target: i64,
) -> anyhow::Result<()> {
    let start = std::time::Instant::now();
    while *current_frame < target {
        if !group.is_alive() {
            anyhow::bail!("Gatherer died at frame {current_frame}, target {target}");
        }
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > *current_frame {
                *current_frame = payload.frame_number;
            }
        }
        if start.elapsed().as_secs() > 120 {
            anyhow::bail!("Timed out at frame {current_frame}, target {target}");
        }
        *polls += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
    Ok(())
}

/// Decode the first camera's raw JPEG frame to RGB and compute mean luminance.
///
/// Uses the on-demand raw frames slot (zero overhead on the hot path).
/// Returns mean ITU-R BT.601 luminance 0–255 (0=black, 255=white).
/// Returns -1.0 on failure.
fn capture_brightness_sample(group: &CameraGroup) -> f64 {
    for _ in 0..10 {
        if let Some(frames) = group.latest_raw_frames() {
            if let Some(first) = frames.first() {
                if first.jpeg_bytes.is_empty() {
                    std::thread::sleep(std::time::Duration::from_millis(10));
                    continue;
                }
                match skellycam::decode::mjpeg_to_rgb(&first.jpeg_bytes) {
                    Ok((_w, _h, rgb)) => {
                        return skellycam::decode::mean_luminance(&rgb);
                    }
                    Err(e) => {
                        tracing::warn!("Failed to decode JPEG for brightness sample: {e}");
                        return -1.0;
                    }
                }
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    -1.0
}
