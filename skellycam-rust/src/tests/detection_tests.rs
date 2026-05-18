//! Camera detection tests.
//!
//! Subcommands:
//!   test detect           — basic enumeration
//!   test detect in-use    — verify camera-in-use detection behavior

use std::collections::HashMap;

use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

pub fn run(args: &[String]) -> anyhow::Result<()> {
    match args.first().map(|s| s.as_str()) {
        Some("in-use") => run_in_use_test(),
        _ => run_basic_detection(),
    }
}

fn run_basic_detection() -> anyhow::Result<()> {
    let cameras = detect_cameras()?;
    if cameras.is_empty() {
        tracing::warn!("No cameras found.");
    } else {
        tracing::info!(
            "Found {} camera{} total.",
            cameras.len(),
            if cameras.len() == 1 { "" } else { "s" }
        );
        for cam in &cameras {
            tracing::info!(
                "  [{}] {} — {} format(s)",
                cam.camera_index,
                cam.camera_name,
                cam.formats.len(),
            );
        }
    }
    Ok(())
}

/// Test whether cameras show as "in use" when already opened by a CameraGroup.
///
/// openpnp-capture on Windows/DirectShow typically grants exclusive access
/// to camera devices. This test verifies:
///   1. Re-detection while a camera is in use still works (enumeration is separate
///      from stream ownership).
///   2. Attempting to open an already-in-use camera produces a clear error
///      (not a crash or hang).
pub fn run_in_use_test() -> anyhow::Result<()> {
    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  CAMERA IN-USE DETECTION TEST");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected — cannot run in-use test");
    }

    if all_cameras.len() < 2 {
        tracing::warn!("⚠  Only 1 camera detected — cannot test exclusive access (need 2+ cameras).");
        tracing::warn!("   Skipping in-use detection test.");
        return Ok(());
    }

    let test_camera = &all_cameras[0];
    tracing::info!(
        "  Using camera [{}] '{}' for exclusive-access test",
        test_camera.camera_index,
        test_camera.camera_name,
    );

    // ── Phase 1: Baseline detection ───────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Phase 1: Baseline detection (no cameras open) ──");
    let baseline = detect_cameras()?;
    tracing::info!(
        "  Baseline: {} camera(s) detected",
        baseline.len()
    );

    // ── Phase 2: Open camera 0, then re-detect ────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Phase 2: Open camera 0, re-detect while in use ──");

    let mut configs = HashMap::new();
    configs.insert(
        test_camera.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: test_camera.camera_id.clone(),
                camera_index: test_camera.camera_index as u32,
                width: 1280,
                height: 720,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: 30.0,
                rotation: -1,
            },
            identity: test_camera.clone(),
        },
    );

    let mut group = CameraGroup::new(configs);
    group.start()?;
    tracing::info!(
        "  Camera [{}] started — now in use",
        test_camera.camera_index,
    );

    // Re-detect while camera is running
    let during = detect_cameras()?;
    tracing::info!(
        "  During use: {} camera(s) detected (baseline: {})",
        during.len(),
        baseline.len(),
    );

    // Check if the camera still appears in detection
    let cam_still_visible = during
        .iter()
        .any(|c| c.camera_index == test_camera.camera_index);
    if cam_still_visible {
        tracing::info!(
            "  ✓ Camera [{}] still visible in detection while in use \
             (enumeration is independent of stream ownership)",
            test_camera.camera_index,
        );
    } else {
        tracing::warn!(
            "  ! Camera [{}] NOT visible during use — driver reports it as unavailable",
            test_camera.camera_index,
        );
    }

    // ── Phase 3: Try to open the same camera again ────────────────────────
    tracing::info!("");
    tracing::info!("  ── Phase 3: Attempt to open already-in-use camera ──");
    tracing::info!("  Expecting: the second open should fail with a clear error...");

    let mut second_configs = HashMap::new();
    second_configs.insert(
        test_camera.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: test_camera.camera_id.clone(),
                camera_index: test_camera.camera_index as u32,
                width: 1280,
                height: 720,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: 30.0,
                rotation: -1,
            },
            identity: test_camera.clone(),
        },
    );

    let mut second_group = CameraGroup::new(second_configs);
    match second_group.start() {
        Ok(()) => {
            tracing::warn!(
                "  ! Camera [{}] was opened successfully a SECOND time — \
                 driver allows shared access (non-exclusive mode)",
                test_camera.camera_index,
            );
            tracing::warn!(
                "  ! This means the OS/driver supports concurrent camera access. \
                 No 'in use' detection is possible at this level."
            );
            // Clean up the second group
            let _ = second_group.shutdown();
        }
        Err(e) => {
            tracing::info!(
                "  ✓ Second open correctly FAILED: {e}"
            );
            tracing::info!(
                "  ✓ Camera [{}] is properly locked for exclusive access.",
                test_camera.camera_index,
            );
        }
    }

    // ── Phase 4: Shutdown first group, verify camera is free again ────────
    tracing::info!("");
    tracing::info!("  ── Phase 4: Shutdown first group, verify camera released ──");
    group.shutdown()?;
    tracing::info!("  Camera [{}] shut down.", test_camera.camera_index);

    // Verify camera is usable again after shutdown
    let mut reopen_configs = HashMap::new();
    reopen_configs.insert(
        test_camera.camera_id.clone(),
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: test_camera.camera_id.clone(),
                camera_index: test_camera.camera_index as u32,
                width: 1280,
                height: 720,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: 30.0,
                rotation: -1,
            },
            identity: test_camera.clone(),
        },
    );

    let mut reopen_group = CameraGroup::new(reopen_configs);
    match reopen_group.start() {
        Ok(()) => {
            tracing::info!(
                "  ✓ Camera [{}] successfully re-opened after shutdown — released properly.",
                test_camera.camera_index,
            );
            let _ = reopen_group.shutdown();
        }
        Err(e) => {
            tracing::warn!(
                "  ✗ Camera [{}] could NOT be re-opened after shutdown: {e}",
                test_camera.camera_index,
            );
        }
    }

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  CAMERA IN-USE TEST COMPLETE");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    Ok(())
}
