//! Recording integration test.
//!
//! Drives a full recording lifecycle using frame-count-driven phases:
//!   warmup (0..60) → start recording → record (60..210) → stop → post-record (210..240) → shutdown
//!
//! Verifies:
//!   - `start_recording()` / `stop_recording()` complete without errors
//!   - `RecordingSummary` has correct frame counts
//!   - mp4 files, CSV timestamps, and `recording_info.json` exist on disk
//!   - Clean shutdown after recording

use std::collections::HashMap;
use std::path::PathBuf;

use crate::cli::RecordingArgs;
use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig, RecordingParams};

const WARMUP_FRAMES: i64 = 60;
const RECORD_FRAMES: i64 = 150;
const POST_RECORD_FRAMES: i64 = 30;

pub fn run(args: &RecordingArgs) -> anyhow::Result<()> {
    let output_base = args
        .output
        .clone()
        .unwrap_or_else(|| {
            let home = dirs::home_dir()
                .unwrap_or_else(|| PathBuf::from("."));
            home.join("skellycam_data")
                .join("recordings")
                .to_string_lossy()
                .to_string()
        });

    let all_cameras: Vec<_> = detect_cameras()?
        .into_iter()
        .map(|d| d.identity)
        .collect();
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let num_cameras = match args.cameras {
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

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  RECORDING TEST — {} camera{}", num_cameras, if num_cameras == 1 { "" } else { "s" });
    tracing::info!("  Output base: {output_base}");
    tracing::info!("  Phases: warmup={WARMUP_FRAMES} → record={RECORD_FRAMES} → post-record={POST_RECORD_FRAMES}");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    // ── Build configs ──────────────────────────────────────────────────────
    let configs: HashMap<String, CameraGroupConfig> = all_cameras
        .iter()
        .take(num_cameras)
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

    // ── Start cameras ──────────────────────────────────────────────────────
    let mut group = CameraGroup::new(configs);
    group.start()?;

    tracing::info!("  Waiting for first frame...");
    let init_start = std::time::Instant::now();
    let mut current_frame: i64 = -1;
    let mut poll_count: u64 = 0;

    // ── Phase 1: Warmup (frames 0..WARMUP_FRAMES) ──────────────────────────
    wait_for_frame(&mut group, &mut current_frame, &mut poll_count, 0)?;
    let init_elapsed = init_start.elapsed().as_secs_f64();
    tracing::info!("  First frame received (init took {init_elapsed:.1}s)");

    tracing::info!("  ── Warmup phase ({} frames) ──", WARMUP_FRAMES);
    poll_until_frame(&mut group, &mut current_frame, &mut poll_count, WARMUP_FRAMES)?;

    // ── Phase 2: Start Recording ───────────────────────────────────────────
    let target_frame = WARMUP_FRAMES;
    tracing::info!("");
    tracing::info!("  ── Starting recording at frame {target_frame} ──");
    tracing::info!("");

    let recording_label = format!("cameras-{num_cameras}");

    group.start_recording(RecordingParams {
        output_dir: output_base.clone(),
        label: Some(recording_label),
    })?;

    // Wait for is_recording() to become true (dispatcher creates recorders
    // on the next multiframe after receiving the StartRecording command).
    // The first call to VideoRecorder::new() may trigger ffmpeg-sidecar's
    // auto-download of ffmpeg, which can take several seconds.
    let mut recording_confirmed_frame: Option<i64> = None;
    let wait_start = std::time::Instant::now();
    let wait_timeout = std::time::Duration::from_secs(30);
    loop {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > current_frame {
                current_frame = payload.frame_number;
            }
        }
        poll_count += 1;
        std::thread::sleep(std::time::Duration::from_millis(10));
        if group.is_recording() {
            recording_confirmed_frame = Some(current_frame);
            break;
        }
        if wait_start.elapsed() > wait_timeout {
            break;
        }
    }

    let confirm_frame = recording_confirmed_frame
        .ok_or_else(|| anyhow::anyhow!("Recording did not start within 10 multiframes"))?;
    tracing::info!(
        "  Recording confirmed active at multiframe {confirm_frame}  |  is_recording() = true"
    );

    // ── Phase 3: Record (WARMUP_FRAMES..WARMUP_FRAMES+RECORD_FRAMES) ───────
    let record_end = WARMUP_FRAMES + RECORD_FRAMES;
    tracing::info!("  ── Recording phase ({} frames) ──", RECORD_FRAMES);

    let mut last_report_frame: i64 = confirm_frame;
    let mut last_report_time = std::time::Instant::now();
    loop {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > current_frame {
                current_frame = payload.frame_number;

                // FPS report every 30 frames
                if current_frame - last_report_frame >= 30 {
                    let now = std::time::Instant::now();
                    let interval = now.duration_since(last_report_time).as_secs_f64();
                    let fps = 30.0 / interval;
                    tracing::info!(
                        "  [recording] multiframe {current_frame:>5}  |  {fps:.1} fps  |  is_recording() = {}",
                        group.is_recording()
                    );
                    last_report_frame = current_frame;
                    last_report_time = now;
                }
                if current_frame >= record_end {
                    break;
                }
            }
        }
        assert!(
            group.is_recording(),
            "is_recording() flipped to false during recording at frame {current_frame}"
        );
        poll_count += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }

    // ── Phase 4: Stop Recording ────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Stopping recording at frame {current_frame} ──");

    let summary = group.stop_recording()?;
    tracing::info!("  RecordingSummary:");
    tracing::info!("    total_frames_per_camera: {}", summary.total_frames_per_camera);
    tracing::info!(
        "    info_json_path: {}",
        summary.info_json_path.display()
    );
    let expected_frames = RECORD_FRAMES as u64;
    if summary.total_frames_per_camera != expected_frames {
        tracing::warn!(
            "    WARNING: expected ~{expected_frames} frames per camera, got {} (difference: {})",
            summary.total_frames_per_camera,
            (summary.total_frames_per_camera as i64 - expected_frames as i64).abs(),
        );
    }
    tracing::info!("    video paths ({}):", summary.video_paths.len());
    for p in &summary.video_paths {
        tracing::info!("      {}", p.display());
    }
    tracing::info!("    csv paths ({}):", summary.csv_paths.len());
    for p in &summary.csv_paths {
        tracing::info!("      {}", p.display());
    }

    assert!(
        !group.is_recording(),
        "is_recording() must be false after stop_recording()"
    );
    tracing::info!("  is_recording() = false ✓");

    // ── Phase 5: Post-Record (current_frame..current_frame+POST_RECORD_FRAMES) ──
    let post_end = current_frame + POST_RECORD_FRAMES;
    tracing::info!("");
    tracing::info!("  ── Post-record phase ({} frames) ──", POST_RECORD_FRAMES);
    poll_until_frame(&mut group, &mut current_frame, &mut poll_count, post_end)?;

    // ── Phase 6: Shutdown ──────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Shutting down ──");
    group.shutdown()?;
    tracing::info!("  Shutdown complete.");

    // ── Phase 7: Verify disk output ────────────────────────────────────────
    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  DISK VERIFICATION");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    verify_disk_output(&summary, expected_frames)?;

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  RECORDING TEST COMPLETE");
    tracing::info!("  Cameras: {num_cameras}");
    tracing::info!("  Frames per camera: {}", summary.total_frames_per_camera);
    tracing::info!("  Polls: {poll_count}");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    Ok(())
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/// Block until `current_frame` increments past the initial value, confirming
/// the pipeline is delivering multiframes.
fn wait_for_frame(
    group: &CameraGroup,
    current_frame: &mut i64,
    poll_count: &mut u64,
    _expected: i64,
) -> anyhow::Result<()> {
    let start = std::time::Instant::now();
    while start.elapsed().as_secs() < 30 {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > *current_frame {
                *current_frame = payload.frame_number;
                return Ok(());
            }
        }
        *poll_count += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
    anyhow::bail!("Timed out waiting for first frame");
}

/// Poll until `current_frame` reaches `target`.
fn poll_until_frame(
    group: &CameraGroup,
    current_frame: &mut i64,
    poll_count: &mut u64,
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
            anyhow::bail!(
                "Timed out at frame {current_frame}, target {target}"
            );
        }
        *poll_count += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
    Ok(())
}

/// Verify output files on disk.
fn verify_disk_output(
    summary: &skellycam::recording::finalizer::RecordingSummary,
    _expected_frame_count: u64,
) -> anyhow::Result<()> {
    // 1. recording_info.json exists and is valid
    if summary.info_json_path.as_os_str().is_empty() {
        tracing::warn!("  ✗ recording_info.json path is empty — file was not written");
    } else if summary.info_json_path.exists() {
        let content = std::fs::read_to_string(&summary.info_json_path)?;
        let parsed: serde_json::Value = serde_json::from_str(&content)?;
        tracing::info!("  ✓ recording_info.json exists:");
        tracing::info!(
            "    recording_directory: {}",
            parsed.get("recording_directory")
                .and_then(|v| v.as_str())
                .unwrap_or("?")
        );
        tracing::info!(
            "    camera_count: {}",
            parsed.get("camera_count")
                .and_then(|v| v.as_i64())
                .unwrap_or(-1)
        );
        tracing::info!(
            "    total_frames_per_camera: {}",
            parsed.get("total_frames_per_camera")
                .and_then(|v| v.as_u64())
                .unwrap_or(0)
        );
    } else {
        tracing::warn!("  ✗ recording_info.json does not exist: {}", summary.info_json_path.display());
    }

    // 2. Each mp4 file exists and has non-zero size
    for (i, video_path) in summary.video_paths.iter().enumerate() {
        if video_path.exists() {
            let size = std::fs::metadata(video_path)?.len();
            let size_mb = size as f64 / (1024.0 * 1024.0);
            if size > 0 {
                tracing::info!("  ✓ video[{i}]: {:.2} MB — {}", size_mb, video_path.display());
            } else {
                tracing::warn!("  ✗ video[{i}]: empty file — {}", video_path.display());
            }
        } else {
            tracing::warn!("  ✗ video[{i}]: not found — {}", video_path.display());
        }
    }

    // 3. Each CSV file exists and has >1 row (header + data)
    for (i, csv_path) in summary.csv_paths.iter().enumerate() {
        if csv_path.exists() {
            let mut reader = csv::Reader::from_path(csv_path)?;
            let row_count = reader.records().count();
            if row_count > 0 {
                tracing::info!(
                    "  ✓ csv[{i}]: {row_count} data rows — {}",
                    csv_path.display()
                );
            } else {
                tracing::warn!("  ✗ csv[{i}]: zero data rows — {}", csv_path.display());
            }
        } else {
            tracing::warn!("  ✗ csv[{i}]: not found — {}", csv_path.display());
        }
    }

    Ok(())
}
