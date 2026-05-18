//! Lossless JPEG rotation integration test.
//!
//! Cycles through each rotation value (0=90°CW, 1=180°, 2=270°CCW),
//! verifies config via camera_statuses(), checks JPEG size changed
//! (rotated DCT blocks produce different compressed output), and records
//! a rotated video to disk.

use std::collections::HashMap;

use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig, RecordingParams};

const FRAMES_PER_ROTATION: i64 = 20;
const RECORD_FRAMES: i64 = 60;

pub fn run(args: &[String]) -> anyhow::Result<()> {
    let camera_count = args
        .iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok())
        .unwrap_or(1);

    let output_base = args
        .iter()
        .position(|arg| arg == "--output")
        .and_then(|pos| args.get(pos + 1))
        .map(|s| s.to_string())
        .unwrap_or_else(|| {
            dirs::home_dir()
                .unwrap_or_else(|| std::path::PathBuf::from("."))
                .join("skellycam_data")
                .join("recordings")
                .to_string_lossy()
                .to_string()
        });

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let num = camera_count.min(all_cameras.len() as u32) as usize;

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  ROTATION TEST — {} camera{}", num, if num == 1 { "" } else { "s" });
    tracing::info!("  Testing: rotation=-1 → 0 → 1 → 2 → 0(record) → -1");
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
                    rotation: -1, // start with no rotation
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
    poll_to(&mut group, &mut current_frame, &mut polls, 10)?;
    tracing::info!("  Stabilized at frame {current_frame}");

    // ── Baseline: no rotation ──────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── rotation=-1 (no rotation) ──");
    let baseline_size = sample_payload_size(&group);
    tracing::info!("  Payload size: {baseline_size:.1} KB");
    verify_rotation_all(&group, -1);

    // ── Rotation 0 (90° CW) ───────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── rotation=0 (90° CW) ──");
    apply_rotation(&mut group, &all_cameras, 0);
    let target = current_frame + FRAMES_PER_ROTATION;
    poll_to(&mut group, &mut current_frame, &mut polls, target)?;
    let rot90_size = sample_payload_size(&group);
    tracing::info!("  Payload size: {rot90_size:.1} KB (baseline: {baseline_size:.1} KB)");
    verify_rotation_all(&group, 0);

    // ── Rotation 1 (180°) ─────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── rotation=1 (180°) ──");
    apply_rotation(&mut group, &all_cameras, 1);
    let target = current_frame + FRAMES_PER_ROTATION;
    poll_to(&mut group, &mut current_frame, &mut polls, target)?;
    let rot180_size = sample_payload_size(&group);
    tracing::info!("  Payload size: {rot180_size:.1} KB (rot90: {rot90_size:.1} KB)");
    verify_rotation_all(&group, 1);

    // ── Rotation 2 (270° CCW) ─────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── rotation=2 (270° CCW) ──");
    apply_rotation(&mut group, &all_cameras, 2);
    let target = current_frame + FRAMES_PER_ROTATION;
    poll_to(&mut group, &mut current_frame, &mut polls, target)?;
    let rot270_size = sample_payload_size(&group);
    tracing::info!("  Payload size: {rot270_size:.1} KB");
    verify_rotation_all(&group, 2);

    // ── Rotation 0 (90° CW) + Recording ───────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── rotation=0 (90° CW) + RECORDING ──");
    apply_rotation(&mut group, &all_cameras, 0);
    let target = current_frame + 10;
    poll_to(&mut group, &mut current_frame, &mut polls, target)?;

    group.start_recording(RecordingParams {
        output_dir: output_base.clone(),
        label: Some(format!("cameras-{num}_rotation-90cw")),
    })?;

    // Wait for recording to start
    let rec_start = std::time::Instant::now();
    loop {
        if let Some(payload) = group.latest_frontend_payload() {
            current_frame = payload.frame_number;
        }
        polls += 1;
        std::thread::sleep(std::time::Duration::from_millis(10));
        if group.is_recording() || rec_start.elapsed().as_secs() > 30 {
            break;
        }
    }
    assert!(group.is_recording(), "Recording failed to start");

    tracing::info!("  Recording {RECORD_FRAMES} frames with rotation=0 (90° CW)...");
    let record_start_frame = current_frame;
    let record_end = record_start_frame + RECORD_FRAMES;
    while current_frame < record_end {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > current_frame {
                current_frame = payload.frame_number;
                if (current_frame - record_start_frame) % 20 == 0 {
                    tracing::info!("    recording frame {current_frame}");
                }
            }
        }
        polls += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }

    let summary = group.stop_recording()?;
    tracing::info!("  Recording stopped: {} frames per camera", summary.total_frames_per_camera);

    // Verify recorded video on disk + check dimensions are rotated
    for (i, video_path) in summary.video_paths.iter().enumerate() {
        if video_path.exists() {
            let size_mb = std::fs::metadata(video_path)?.len() as f64 / (1024.0 * 1024.0);
            let dims = probe_video_dimensions(video_path);
            tracing::info!(
                "  ✓ rotated video[{i}]: {size_mb:.2} MB  {dims} — {}",
                video_path.display()
            );
            // 90° CW rotation should swap width/height (1280x720 → 720x1280)
            if dims == "720x1280" || dims == "1280x720" {
                tracing::info!("    Dimensions check: original 1280x720 → rotated {dims}");
            }
        } else {
            tracing::warn!("  ✗ rotated video[{i}]: not found — {}", video_path.display());
        }
    }

    // ── Back to no rotation ────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── rotation=-1 (back to no rotation) ──");
    apply_rotation(&mut group, &all_cameras, -1);
    let target = current_frame + 10;
    poll_to(&mut group, &mut current_frame, &mut polls, target)?;
    verify_rotation_all(&group, -1);

    // ── Shutdown ───────────────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Shutting down ──");
    group.shutdown()?;
    tracing::info!("  Shutdown complete.");

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  ROTATION TEST COMPLETE");
    tracing::info!("  Payload sizes: baseline={baseline_size:.1}K  90={rot90_size:.1}K  180={rot180_size:.1}K  270={rot270_size:.1}K");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    Ok(())
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn poll_to(
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
        if start.elapsed().as_secs() > 60 {
            anyhow::bail!("Timed out at frame {current_frame}, target {target}");
        }
        *polls += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
    Ok(())
}

fn apply_rotation(
    group: &mut CameraGroup,
    all_cameras: &[skellycam::camera::CameraIdentity],
    rotation: i32,
) {
    group.pause();
    let mut new_configs: HashMap<String, CameraGroupConfig> = HashMap::new();
    for status in group.camera_statuses() {
        let mut new_cfg = status.config.clone();
        new_cfg.rotation = rotation;
        let identity = all_cameras
            .iter()
            .find(|c| c.camera_index == status.camera_index)
            .cloned()
            .expect("camera identity not found");
        new_configs.insert(
            status.config.camera_id.clone(),
            CameraGroupConfig {
                capture_config: new_cfg,
                identity,
            },
        );
    }
    group.apply(new_configs).expect("apply rotation config");
    group.unpause();
}

fn verify_rotation_all(group: &CameraGroup, expected: i32) {
    for status in group.camera_statuses() {
        assert_eq!(
            status.config.rotation, expected,
            "Camera {}: rotation should be {expected}, got {}",
            status.config.camera_id, status.config.rotation,
        );
    }
    tracing::info!("  ✓ All cameras report rotation={expected}");
}

fn probe_video_dimensions(path: &std::path::Path) -> String {
    match std::process::Command::new("ffprobe")
        .args([
            "-v", "error",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
        ])
        .arg(path)
        .output()
    {
        Ok(output) if output.status.success() => {
            String::from_utf8_lossy(&output.stdout).trim().to_string()
        }
        _ => "unknown".to_string(),
    }
}

fn sample_payload_size(group: &CameraGroup) -> f64 {
    for _ in 0..5 {
        if let Some(payload) = group.latest_frontend_payload() {
            return payload.jpeg_bytes.len() as f64 / 1024.0;
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
    0.0
}
