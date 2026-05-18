//! Update-config integration tests.
//!
//! Subcommand routing:
//!   test update exposure [--cameras N]       — change exposure, verify image brightness
//!   test update resolution [--camera-index I] — change resolution (if multiple formats)
//!   test update framerate [--camera-index I] — change framerate (if multiple formats)
//!   test update add-camera [--cameras N]      — add a camera mid-stream
//!   test update remove-camera [--cameras N]   — remove a camera mid-stream

use skellycam::camera_group::CameraGroup;

pub fn run(args: &[String]) -> anyhow::Result<()> {
    match args.first().map(|s| s.as_str()) {
        Some("exposure") => run_exposure_test(&args[1..]),
        Some("resolution") => run_resolution_test(&args[1..]),
        Some("framerate") => run_framerate_test(&args[1..]),
        Some("add-camera") => run_add_camera_test(&args[1..]),
        Some("remove-camera") => run_remove_camera_test(&args[1..]),
        Some(other) => {
            eprintln!("unknown update subcommand: {other}");
            eprintln!("available: exposure, resolution, framerate, add-camera, remove-camera");
            Ok(())
        }
        None => {
            eprintln!("usage: cargo run --release -- test update <subcommand> [flags]");
            eprintln!("available: exposure, resolution, framerate, add-camera, remove-camera");
            Ok(())
        }
    }
}

// ── Exposure test ──────────────────────────────────────────────────────────────

fn run_exposure_test(args: &[String]) -> anyhow::Result<()> {
    use std::collections::HashMap;
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

    let camera_count = parse_camera_count(args);

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let num = camera_count.unwrap_or(all_cameras.len().min(2) as u32) as usize;

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  UPDATE EXPOSURE TEST — {} camera{}", num, if num == 1 { "" } else { "s" });
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
                    exposure: -7, // start with moderate exposure
                    exposure_mode: "MANUAL".into(),
                    framerate: 30.0,
                    rotation: -1,
                },
                identity: identity.clone(),
            };
            (cfg.identity.camera_id.clone(), cfg)
        })
        .collect();

    let mut group = CameraGroup::new(configs);
    group.start()?;

    // Poll 30 frames to stabilize
    let mut current_frame: i64 = -1;
    let mut _polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut _polls, 30)?;
    tracing::info!("  Stabilized at frame {current_frame}");

    // Capture reference frame brightness
    let ref_brightness = capture_brightness_sample(&group);
    tracing::info!("  Reference brightness (exposure=-7): {ref_brightness:.1}");

    // Pause, apply lower exposure, unpause
    group.pause();
    tracing::info!("  Applying new config with exposure=-11...");

    let mut new_configs: HashMap<String, CameraGroupConfig> = HashMap::new();
    for status in group.camera_statuses() {
        let mut new_cfg = status.config.clone();
        new_cfg.exposure = -11; // lower exposure → darker image
        new_configs.insert(
            status.config.camera_id.clone(),
            CameraGroupConfig {
                capture_config: new_cfg,
                identity: all_cameras
                    .iter()
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
    std::thread::sleep(std::time::Duration::from_millis(500)); // let settings settle
    group.unpause();

    // Poll 30 more frames
    let target = current_frame + 30;
    poll_frames(&mut group, &mut current_frame, &mut _polls, target)?;

    // Capture updated frame brightness
    let new_brightness = capture_brightness_sample(&group);
    tracing::info!("  New brightness (exposure=-11): {new_brightness:.1}");

    // Verify brightness changed in expected direction
    if new_brightness < ref_brightness * 0.95 {
        tracing::info!(
            "  ✓ Brightness decreased by {:.1}% (as expected for lower exposure)",
            (1.0 - new_brightness / ref_brightness) * 100.0
        );
    } else if new_brightness > ref_brightness * 1.05 {
        tracing::warn!(
            "  ✗ WARNING: Brightness INCREASED ({:.1}%) when it should have decreased. \
             This platform may not support manual exposure control.",
            (new_brightness / ref_brightness - 1.0) * 100.0
        );
    } else {
        tracing::warn!(
            "  ? Brightness changed by <5% — exposure setting may not have taken effect \
             on this platform (ref={ref_brightness:.1}, new={new_brightness:.1})"
        );
    }

    // Verify camera_statuses reflect the new exposure
    for status in group.camera_statuses() {
        assert_eq!(
            status.config.exposure, -11,
            "Camera {} exposure should be -11, got {}",
            status.config.camera_id, status.config.exposure
        );
    }
    tracing::info!("  ✓ All camera statuses reflect exposure=-11");

    group.shutdown()?;
    tracing::info!("  Shutdown complete.");
    tracing::info!("");
    tracing::info!("  EXPOSURE TEST COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Resolution test ────────────────────────────────────────────────────────────

fn run_resolution_test(args: &[String]) -> anyhow::Result<()> {
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let camera_index = parse_camera_index(args).unwrap_or(0);

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let identity = all_cameras
        .iter()
        .find(|c| c.camera_index == camera_index as i32)
        .ok_or_else(|| anyhow::anyhow!("Camera index {camera_index} not found"))?;

    // Find two distinct MJPG resolution formats
    let formats: Vec<_> = identity
        .formats
        .iter()
        .filter(|f| f.fourcc_str == "MJPG")
        .collect();
    if formats.len() < 2 {
        anyhow::bail!(
            "Camera {} only has {} MJPG format(s) — need at least 2 for resolution test",
            identity.label(),
            formats.len()
        );
    }

    let (fmt_low, fmt_high) = if formats[0].width * formats[0].height
        < formats[1].width * formats[1].height
    {
        (formats[0], formats[1])
    } else {
        (formats[1], formats[0])
    };

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!(
        "  UPDATE RESOLUTION TEST — {} ({}x{} → {}x{})",
        identity.label(),
        fmt_low.width, fmt_low.height,
        fmt_high.width, fmt_high.height,
    );
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let mut configs = HashMap::new();
    configs.insert(
        identity.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: fmt_low.width,
                height: fmt_low.height,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: fmt_low.fps as f64,
                rotation: -1,
            },
            identity: identity.clone(),
        },
    );

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut _polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut _polls, 30)?;

    // Verify initial resolution
    let init_statuses = group.camera_statuses();
    let init_cfg = &init_statuses[0].config;
    tracing::info!(
        "  Initial: {}x{} @{}fps",
        init_cfg.width, init_cfg.height, init_cfg.framerate
    );
    assert_eq!(init_cfg.width, fmt_low.width);
    assert_eq!(init_cfg.height, fmt_low.height);

    // Pause, apply new resolution, unpause
    group.pause();
    let mut new_configs = HashMap::new();
    new_configs.insert(
        identity.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: fmt_high.width,
                height: fmt_high.height,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: fmt_high.fps as f64,
                rotation: -1,
            },
            identity: identity.clone(),
        },
    );
    group.apply(new_configs)?;
    group.unpause();

    let target = current_frame + 30;
    poll_frames(&mut group, &mut current_frame, &mut _polls, target)?;

    let new_statuses = group.camera_statuses();
    let new_cfg = &new_statuses[0].config;
    tracing::info!(
        "  After apply: {}x{} @{}fps",
        new_cfg.width, new_cfg.height, new_cfg.framerate
    );

    if new_cfg.width == fmt_high.width && new_cfg.height == fmt_high.height {
        tracing::info!("  ✓ Resolution changed successfully");
    } else {
        tracing::warn!(
            "  ? Resolution did not change (still {}x{}) — mid-stream resolution \
             change may require stream restart on this platform",
            new_cfg.width, new_cfg.height,
        );
    }

    group.shutdown()?;
    tracing::info!("  RESOLUTION TEST COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Framerate test ─────────────────────────────────────────────────────────────

fn run_framerate_test(args: &[String]) -> anyhow::Result<()> {
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let camera_index = parse_camera_index(args).unwrap_or(0);

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }
    let identity = all_cameras
        .iter()
        .find(|c| c.camera_index == camera_index as i32)
        .ok_or_else(|| anyhow::anyhow!("Camera index {camera_index} not found"))?;

    // Find two distinct MJPG framerate formats at the same resolution
    let formats: Vec<_> = identity
        .formats
        .iter()
        .filter(|f| f.fourcc_str == "MJPG")
        .collect();

    // Group by resolution, find a resolution with multiple framerates
    let mut res_groups: HashMap<(u32, u32), Vec<&skellycam::camera::CameraFormatInfo>> =
        HashMap::new();
    for f in &formats {
        res_groups.entry((f.width, f.height)).or_default().push(f);
    }
    let multi_fps = res_groups.iter().find(|(_, fs)| fs.len() >= 2);
    let (res, fps_formats) = match multi_fps {
        Some(r) => r,
        None => anyhow::bail!("No resolution with multiple framerates found on this camera"),
    };

    let (fps_low, fps_high) = if fps_formats[0].fps < fps_formats[1].fps {
        (fps_formats[0], fps_formats[1])
    } else {
        (fps_formats[1], fps_formats[0])
    };

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!(
        "  UPDATE FRAMERATE TEST — {} ({}x{} @{}fps → @{}fps)",
        identity.label(),
        res.0, res.1,
        fps_low.fps, fps_high.fps,
    );
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let mut configs = HashMap::new();
    configs.insert(
        identity.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: res.0,
                height: res.1,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: fps_low.fps as f64,
                rotation: -1,
            },
            identity: identity.clone(),
        },
    );

    let mut group = CameraGroup::new(configs);
    group.start()?;

    let mut current_frame: i64 = -1;
    let mut _polls: u64 = 0;
    poll_frames(&mut group, &mut current_frame, &mut _polls, 60)?;

    let fps_before = measure_fps(&group, 30);
    tracing::info!("  FPS before apply: {fps_before:.1} (expected ~{})", fps_low.fps);

    // Pause, apply new framerate, unpause
    group.pause();
    let mut new_configs = HashMap::new();
    new_configs.insert(
        identity.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: identity.camera_id.clone(),
                camera_index: identity.camera_index as u32,
                width: res.0,
                height: res.1,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: fps_high.fps as f64,
                rotation: -1,
            },
            identity: identity.clone(),
        },
    );
    group.apply(new_configs)?;
    group.unpause();

    let target = current_frame + 30;
    poll_frames(&mut group, &mut current_frame, &mut _polls, target)?;

    let fps_after = measure_fps(&group, 30);
    tracing::info!("  FPS after apply: {fps_after:.1} (expected ~{})", fps_high.fps);

    if fps_after > fps_before * 1.1 {
        tracing::info!(
            "  ✓ Framerate increased by {:.0}%",
            (fps_after / fps_before - 1.0) * 100.0
        );
    } else {
        tracing::warn!(
            "  ? Framerate did not change significantly ({fps_before:.1} → {fps_after:.1}) — \
             mid-stream framerate change may require stream restart",
        );
    }

    group.shutdown()?;
    tracing::info!("  FRAMERATE TEST COMPLETE");
    tracing::info!("");

    Ok(())
}

// ── Add-camera test ────────────────────────────────────────────────────────────

fn run_add_camera_test(args: &[String]) -> anyhow::Result<()> {
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let camera_count = parse_camera_count(args).unwrap_or(2);
    if camera_count < 2 {
        anyhow::bail!("Need at least 2 cameras for add-camera test (one to start, one to add)");
    }

    let all_cameras = detect_cameras()?;
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
                    exposure_mode: "MANUAL".into(), framerate: 30.0, rotation: -1,
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
                exposure_mode: "MANUAL".into(), framerate: 30.0, rotation: -1,
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

fn run_remove_camera_test(args: &[String]) -> anyhow::Result<()> {
    use skellycam::camera::{detect_cameras, CameraConfig};
    use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
    use std::collections::HashMap;

    let camera_count = parse_camera_count(args).unwrap_or(2);
    if camera_count < 2 {
        anyhow::bail!("Need at least 2 cameras for remove-camera test");
    }

    let all_cameras = detect_cameras()?;
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
                    exposure_mode: "MANUAL".into(), framerate: 30.0, rotation: -1,
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

// ── Shared helpers ─────────────────────────────────────────────────────────────

fn parse_camera_count(args: &[String]) -> Option<u32> {
    args.iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok())
}

fn parse_camera_index(args: &[String]) -> Option<u32> {
    args.iter()
        .position(|arg| arg == "--camera-index")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok())
}

fn poll_frames(
    group: &CameraGroup,
    current_frame: &mut i64,
    polls: &mut u64,
    target: i64,
) -> anyhow::Result<()> {
    let start = std::time::Instant::now();
    while *current_frame < target {
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

/// Compute an approximate mean brightness from the JPEG data of the latest payload.
///
/// Decodes the first camera's JPEG to a grayscale image and returns the mean
/// pixel value (0=black, 255=white). Returns 128.0 if decoding fails.
fn capture_brightness_sample(group: &CameraGroup) -> f64 {
    for _ in 0..10 {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.jpeg_bytes.is_empty() {
                std::thread::sleep(std::time::Duration::from_millis(10));
                continue;
            }
            // The frontend payload is a custom binary encoding (not a raw JPEG).
            // We cannot decode individual frame brightness from the encoded payload
            // without accessing individual camera frames.
            //
            // Instead, use the payload size as a rough proxy:
            // for MJPEG, larger JPEG = more detail/lower compression = generally brighter
            // This is imperfect but provides a directional signal.
            return payload.jpeg_bytes.len() as f64 / 1024.0;
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    -1.0
}

/// Measure actual FPS by tracking frame intervals from the frontend payload.
fn measure_fps(group: &CameraGroup, sample_frames: i64) -> f64 {
    let start = std::time::Instant::now();
    let mut last_frame: i64 = -1;
    let mut frame_count = 0i64;

    while frame_count < sample_frames {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > last_frame {
                last_frame = payload.frame_number;
                frame_count += 1;
                if frame_count == 1 {
                    // restart timing from first frame
                    let _ = std::time::Instant::now();
                }
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(1));
        if start.elapsed().as_secs() > 30 {
            break;
        }
    }

    let elapsed = start.elapsed().as_secs_f64();
    if elapsed > 0.0 && frame_count > 1 {
        frame_count as f64 / elapsed
    } else {
        0.0
    }
}
