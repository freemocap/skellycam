//! Orchestrated test suite — runs each test module sequentially with
//! increasing camera counts from 1 up to the total available.
//!
//! Usage:
//!   cargo run --release -- test all [--max-cameras N]
//!
//! Each iteration creates a fresh CameraGroup, runs the applicable tests,
//! and shuts down cleanly before moving to the next camera count.

use crate::cli::{
    AllArgs, CameraCountArgs, FramerateArgs, MultiArgs, RecordingArgs,
    ResolutionArgs, RotateArgs,
};
use skellycam::camera::detect_cameras;

pub fn run(args: &AllArgs) -> anyhow::Result<()> {
    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected — cannot run any tests");
    }
    let total = args
        .max_cameras
        .unwrap_or(all_cameras.len())
        .min(all_cameras.len());

    tracing::info!("");
    tracing::info!("╔══════════════════════════════════════════════════════════════╗");
    tracing::info!("║           SKELLYCAM RUST — FULL TEST SUITE                   ║");
    tracing::info!("╠══════════════════════════════════════════════════════════════╣");
    tracing::info!("║  Cameras detected: {:<43}║", all_cameras.len());
    tracing::info!("║  Test iterations:  1 → {:<43}║", total);
    tracing::info!("╚══════════════════════════════════════════════════════════════╝");
    tracing::info!("");

    if total == 1 {
        tracing::warn!("⚠  Only 1 camera detected — multi-camera tests will be skipped.");
        tracing::info!("");
    }

    let mut passed: Vec<String> = Vec::new();
    let mut failed: Vec<String> = Vec::new();
    let mut skipped: Vec<String> = Vec::new();
    let suite_start = std::time::Instant::now();

    for camera_count in 1..=total {
        tracing::info!("");
        tracing::info!("┌──────────────────────────────────────────────────────────────┐");
        tracing::info!("│  ITERATION {camera_count}/{total}: testing with {camera_count} camera(s){:width$}│",
            "", width = 48_usize.saturating_sub(format!("  ITERATION {camera_count}/{total}: testing with {camera_count} camera(s)").len()));
        tracing::info!("└──────────────────────────────────────────────────────────────┘");
        tracing::info!("");

        let cc = CameraCountArgs { cameras: Some(camera_count) };
        let multi = MultiArgs { cameras: Some(camera_count), indices: None, max_loops: 60 };
        let rec = RecordingArgs { cameras: Some(camera_count), output: None };
        let res = ResolutionArgs { camera_index: 0, sample: 5 };
        let fps_res = FramerateArgs { camera_index: 0, sample: 5 };

        // ── Detect test (always runs) ──────────────────────────────────────
        run_test("detect", &mut passed, &mut failed, || {
            super::detection_tests::run()
        });

        // ── Lifecycle test (start → stream → shutdown) ─────────────────────
        run_test("lifecycle", &mut passed, &mut failed, || {
            super::lifecycle_tests::run(&cc)
        });

        // ── Recording test ─────────────────────────────────────────────────
        run_test("recording", &mut passed, &mut failed, || {
            super::recording_tests::run(&rec)
        });

        // ── Pause test ─────────────────────────────────────────────────────
        run_test("pause", &mut passed, &mut failed, || {
            super::pause_tests::run(&cc)
        });

        // ── Multi-camera streaming (60 frames) ─────────────────────────────
        run_test("multi-camera", &mut passed, &mut failed, || {
            super::multi_camera_tests::run(&multi)
        });

        // ── Exposure test ───────────────────────────────────────────────────
        run_test("update exposure", &mut passed, &mut failed, || {
            super::update_config_tests::run_exposure_test(&cc)
        });

        // ── Multi-camera only tests (require 2+ cameras) ────────────────────
        if camera_count >= 2 {
            run_test("update add-camera", &mut passed, &mut failed, || {
                super::update_config_tests::run_add_camera_test(&cc)
            });

            run_test("update remove-camera", &mut passed, &mut failed, || {
                super::update_config_tests::run_remove_camera_test(&cc)
            });
        } else {
            let multi_tests = ["update add-camera", "update remove-camera"];
            for name in &multi_tests {
                let reason = format!(
                    "{name}  (iteration {camera_count}/{total} — needs 2+ cameras, only {camera_count} available)"
                );
                tracing::warn!("  ⏭  SKIP: {reason}");
                skipped.push(reason);
            }
        }

        // ── Resolution sample (5 evenly spaced across supported formats) ────
        run_test("update resolution", &mut passed, &mut failed, || {
            super::update_config_tests::run_resolution_test(&res)
        });

        // ── Framerate sample (5 evenly spaced across supported formats) ─────
        run_test("update framerate", &mut passed, &mut failed, || {
            super::update_config_tests::run_framerate_test(&fps_res)
        });

        // ── Manager test ───────────────────────────────────────────────────
        run_test("manager", &mut passed, &mut failed, || {
            super::manager_tests::run(&cc)
        });
    }

    // ── Camera-count-independent tests (run once) ───────────────────────────
    tracing::info!("");
    tracing::info!("┌──────────────────────────────────────────────────────────────┐");
    tracing::info!("│  CAMERA-COUNT-INDEPENDENT TESTS                               │");
    tracing::info!("└──────────────────────────────────────────────────────────────┘");
    tracing::info!("");

    run_test("rotate", &mut passed, &mut failed, || {
        super::rotation_tests::run(&RotateArgs { cameras: None, output: None })
    });

    run_test("auto-exposure", &mut passed, &mut failed, || {
        super::update_config_tests::run_auto_exposure_test(
            &CameraCountArgs { cameras: None },
        )
    });

    // ── Summary ──────────────────────────────────────────────────────────
    let elapsed = suite_start.elapsed().as_secs_f64();
    tracing::info!("");
    tracing::info!("╔══════════════════════════════════════════════════════════════════╗");
    tracing::info!("║           SKELLYCAM RUST — TEST SUITE RESULTS                     ║");
    tracing::info!("╠══════════════════════════════════════════════════════════════════╣");
    tracing::info!(
        "║  Cameras:   {:<3} detected,  {:<3} available,   max {:<3} tested             ║",
        all_cameras.len(), all_cameras.len(), total,
    );
    tracing::info!(
        "║  Duration:  {:.0}s  ({:.1} min)                                      ║",
        elapsed, elapsed / 60.0,
    );
    tracing::info!("╠══════════════════════════════════════════════════════════════════╣");
    tracing::info!(
        "║  Iterations: {}  |  Tests per iteration: {}                             ║",
        total,
        passed.len() / total,
    );
    tracing::info!(
        "║  Camera-count-independent tests: {}                                    ║",
        2, // rotate + auto-exposure
    );
    tracing::info!("╠══════════════════════════════════════════════════════════════════╣");
    tracing::info!(
        "║  ✓  {:>3} passed                                                       ║",
        passed.len(),
    );
    tracing::info!(
        "║  ✗  {:>3} failed                                                       ║",
        failed.len(),
    );
    tracing::info!(
        "║  ⏭  {:>3} skipped                                                      ║",
        skipped.len(),
    );
    tracing::info!("╠══════════════════════════════════════════════════════════════════╣");

    if !passed.is_empty() {
        tracing::info!("║                                                                    ║");
        let suffix = if total == 1 { "" } else { "s" };
        tracing::info!("║  Tests run (per iteration, 1→{total} camera{suffix}):{:40}║", "");
        let mut seen: Vec<&str> = Vec::new();
        for name in &passed {
            if !seen.contains(&name.as_str()) {
                seen.push(name.as_str());
            }
        }
        for name in &seen {
            let count = passed.iter().filter(|n| n.as_str() == *name).count();
            tracing::info!("║    ✓  {name:<52}  x{count}  ║");
        }
    }

    if !failed.is_empty() {
        tracing::info!("║                                                                    ║");
        tracing::info!("║  FAILURES:                                                         ║");
        for name in &failed {
            tracing::info!("║    ✗  {name:<56}║");
        }
    }

    if !skipped.is_empty() {
        tracing::info!("║                                                                    ║");
        tracing::info!("║  SKIPPED:                                                          ║");
        for name in &skipped {
            tracing::info!("║    ⏭  {name:<56}║");
        }
    }
    tracing::info!("╚══════════════════════════════════════════════════════════════════╝");
    tracing::info!("");

    if !failed.is_empty() {
        eprintln!(
            "{} test(s) failed: {}",
            failed.len(),
            failed.join(", ")
        );
        std::process::exit(1);
    }

    Ok(())
}

fn run_test(
    name: &str,
    passed: &mut Vec<String>,
    failed: &mut Vec<String>,
    test_fn: impl FnOnce() -> anyhow::Result<()>,
) {
    let start = std::time::Instant::now();
    tracing::info!("  ── {name} ──");
    match test_fn() {
        Ok(()) => {
            let elapsed = start.elapsed().as_secs_f64();
            tracing::info!("  ✓ PASS: {name} ({elapsed:.1}s)");
            passed.push(name.to_string());
        }
        Err(e) => {
            let elapsed = start.elapsed().as_secs_f64();
            tracing::error!("  ✗ FAIL: {name} ({elapsed:.1}s) — {e}");
            failed.push(name.to_string());
        }
    }
    tracing::info!("");
}
