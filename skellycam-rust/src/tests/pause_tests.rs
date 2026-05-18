//! Pause/unpause integration test.
//!
//! Frame-count-driven phases:
//!   warmup (0..60) → pause (60..120) → unpause (120..180) → toggle (180..200) → shutdown
//!
//! Verifies:
//!   - `pause()` stops multiframe delivery (frame number stalls)
//!   - `unpause()` resumes delivery
//!   - `toggle_pause()` correctly flips state
//!   - `is_paused()` matches at each transition

use std::collections::HashMap;

use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};

const WARMUP_FRAMES: i64 = 60;
const PAUSE_FRAMES: i64 = 60;
const UNPAUSE_FRAMES: i64 = 60;
const TOGGLE_FRAMES: i64 = 20;

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

    let num_cameras = match camera_count {
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
        None => all_cameras.len().min(2),
    };

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  PAUSE TEST — {} camera{}", num_cameras, if num_cameras == 1 { "" } else { "s" });
    tracing::info!("  Phases: warmup={WARMUP_FRAMES} → pause={PAUSE_FRAMES} → unpause={UNPAUSE_FRAMES} → toggle={TOGGLE_FRAMES}");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    // ── Build configs and start ────────────────────────────────────────────
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

    let mut group = CameraGroup::new(configs);
    group.start()?;

    tracing::info!("  Waiting for first frame...");
    let mut current_frame: i64 = -1;
    let mut poll_count: u64 = 0;
    poll_until(&mut group, &mut current_frame, &mut poll_count, 1)?;
    let init_frame = current_frame;
    tracing::info!("  First frame received: {init_frame}");

    // ── Phase 1: Warmup ────────────────────────────────────────────────────
    let warmup_end = init_frame + WARMUP_FRAMES;
    tracing::info!("  ── Warmup phase ({} frames) ──", WARMUP_FRAMES);
    poll_until(&mut group, &mut current_frame, &mut poll_count, warmup_end)?;
    assert!(!group.is_paused(), "must not be paused after warmup");
    tracing::info!("  Warmup complete at frame {current_frame}");

    // ── Phase 2: Pause ─────────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Pausing at frame {current_frame} ──");
    group.pause();
    assert!(group.is_paused(), "is_paused() must be true after pause()");

    let pause_start_frame = current_frame;

    // Poll for PAUSE_FRAMES worth of time-equivalent but verify frame
    // number does NOT advance (multiframe delivery suppressed)
    let pause_poll_frames: u64 = (PAUSE_FRAMES * 3) as u64; // 3x margin — we expect frame stalls
    let mut pause_polls: u64 = 0;
    let mut max_frame_during_pause = current_frame;

    while pause_polls < pause_poll_frames {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > max_frame_during_pause {
                max_frame_during_pause = payload.frame_number;
            }
        }
        pause_polls += 1;
        poll_count += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }

    let frame_drift = max_frame_during_pause - pause_start_frame;
    assert!(
        frame_drift <= 3,
        "Frame number advanced by {frame_drift} during pause (must be <= 3) — pause did not stop frames",
    );
    tracing::info!("  Pause verified: frame stalled at ~{pause_start_frame} (drift: {frame_drift} frames in {pause_polls} polls)");

    // ── Phase 3: Unpause ───────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Unpausing at frame {current_frame} ──");
    group.unpause();
    assert!(!group.is_paused(), "is_paused() must be false after unpause()");

    let unpause_end = warmup_end + PAUSE_FRAMES + UNPAUSE_FRAMES;
    tracing::info!("  Resuming, waiting for frame {unpause_end}...");
    poll_until(&mut group, &mut current_frame, &mut poll_count, unpause_end)?;

    let frames_after_unpause = current_frame - pause_start_frame;
    tracing::info!(
        "  Unpause verified: {} frames received after unpausing (expected ~{UNPAUSE_FRAMES})",
        frames_after_unpause,
    );
    assert!(
        !group.is_paused(),
        "is_paused() must still be false after polling"
    );

    // ── Phase 4: Toggle ────────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Toggle pause at frame {current_frame} ──");

    // Toggle ON
    group.toggle_pause();
    assert!(group.is_paused(), "is_paused() must be true after first toggle");
    let toggle_on_frame = current_frame;
    let mut toggle_on_max = current_frame;

    for _ in 0..(TOGGLE_FRAMES * 3) as u64 {
        if let Some(payload) = group.latest_frontend_payload() {
            if payload.frame_number > toggle_on_max {
                toggle_on_max = payload.frame_number;
            }
        }
        poll_count += 1;
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
    let drift_on = toggle_on_max - toggle_on_frame;
    assert!(drift_on <= 3, "Toggle ON: frame drifted by {drift_on} (must be <= 3)");
    tracing::info!("  Toggle ON verified: frame stalled (drift: {drift_on})");

    // Toggle OFF
    group.toggle_pause();
    assert!(!group.is_paused(), "is_paused() must be false after second toggle");

    let toggle_off_target = current_frame + TOGGLE_FRAMES;
    poll_until(&mut group, &mut current_frame, &mut poll_count, toggle_off_target)?;
    tracing::info!("  Toggle OFF verified: frames resumed, now at frame {current_frame}");

    // ── Phase 5: Shutdown ──────────────────────────────────────────────────
    tracing::info!("");
    tracing::info!("  ── Shutting down ──");
    group.shutdown()?;
    tracing::info!("  Shutdown complete.");

    tracing::info!("");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("  PAUSE TEST COMPLETE");
    tracing::info!("  Cameras: {num_cameras}");
    tracing::info!("  Final frame: {current_frame}");
    tracing::info!("  Polls: {poll_count}");
    tracing::info!("══════════════════════════════════════════════════");
    tracing::info!("");

    Ok(())
}

/// Poll until `current_frame` reaches `target`.
fn poll_until(
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
