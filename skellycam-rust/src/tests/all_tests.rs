//! Orchestrated test suite — runs each test module sequentially with
//! increasing camera counts from 1 up to the total available.
//!
//! Usage:
//!   cargo run --release -- test all [--max-cameras N]
//!
//! Each iteration creates a fresh CameraGroup, runs the applicable tests,
//! and shuts down cleanly before moving to the next camera count.

use skellycam::camera::detect_cameras;

pub fn run(args: &[String]) -> anyhow::Result<()> {
    let max_cameras = args
        .iter()
        .position(|arg| arg == "--max-cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<usize>().ok());

    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected — cannot run any tests");
    }
    let total = max_cameras.unwrap_or(all_cameras.len()).min(all_cameras.len());

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

        // ── Detect test (always runs) ──────────────────────────────────────
        run_test("detect", &[], &mut passed, &mut failed, &mut skipped, || {
            super::detection_tests::run(&[])
        });

        // ── Recording test ─────────────────────────────────────────────────
        run_test("recording", &[format!("--cameras={camera_count}")], &mut passed, &mut failed, &mut skipped, || {
            super::recording_tests::run(&[format!("--cameras={camera_count}")])
        });

        // ── Pause test ─────────────────────────────────────────────────────
        run_test("pause", &[format!("--cameras={camera_count}")], &mut passed, &mut failed, &mut skipped, || {
            super::pause_tests::run(&[format!("--cameras={camera_count}")])
        });

        // ── Multi-camera streaming (60 frames) ─────────────────────────────
        run_test("multi-camera", &[format!("--cameras={camera_count}"), "--max-loops=60".into()], &mut passed, &mut failed, &mut skipped, || {
            super::multi_camera_tests::run(
                &[format!("--cameras={camera_count}"), "--max-loops=60".into()]
            )
        });

        // ── Exposure test ───────────────────────────────────────────────────
        run_test("update exposure", &[format!("--cameras={camera_count}")], &mut passed, &mut failed, &mut skipped, || {
            super::update_config_tests::run(&["exposure".into(), format!("--cameras={camera_count}")])
        });

        // ── Multi-camera only tests (require 2+ cameras) ────────────────────
        if camera_count >= 2 {
            run_test("update add-camera", &[format!("--cameras={camera_count}")], &mut passed, &mut failed, &mut skipped, || {
                super::update_config_tests::run(&["add-camera".into(), format!("--cameras={camera_count}")])
            });

            run_test("update remove-camera", &[format!("--cameras={camera_count}")], &mut passed, &mut failed, &mut skipped, || {
                super::update_config_tests::run(&["remove-camera".into(), format!("--cameras={camera_count}")])
            });
        } else {
            let multi_tests = ["update add-camera", "update remove-camera"];
            for name in &multi_tests {
                tracing::warn!("  ⏭  SKIP: {name} (requires 2+ cameras)");
                skipped.push(name.to_string());
            }
        }

        // ── Resolution sample (5 evenly spaced across supported formats) ────
        run_test("update resolution", &[format!("--sample=5")], &mut passed, &mut failed, &mut skipped, || {
            super::update_config_tests::run(&["resolution".into(), "--sample".into(), "5".into()])
        });

        // ── Framerate sample (5 evenly spaced across supported formats) ─────
        run_test("update framerate", &[format!("--sample=5")], &mut passed, &mut failed, &mut skipped, || {
            super::update_config_tests::run(&["framerate".into(), "--sample".into(), "5".into()])
        });

        // ── Manager test ───────────────────────────────────────────────────
        run_test("manager", &[format!("--cameras={camera_count}")], &mut passed, &mut failed, &mut skipped, || {
            super::manager_tests::run(&[format!("--cameras={camera_count}")])
        });
    }

    // ── Camera-count-independent tests (run once) ───────────────────────────
    tracing::info!("");
    tracing::info!("┌──────────────────────────────────────────────────────────────┐");
    tracing::info!("│  CAMERA-COUNT-INDEPENDENT TESTS                               │");
    tracing::info!("└──────────────────────────────────────────────────────────────┘");
    tracing::info!("");

    run_test("rotate", &[], &mut passed, &mut failed, &mut skipped, || {
        super::rotation_tests::run(&[])
    });

    run_test("auto-exposure", &["--cameras=1".into()], &mut passed, &mut failed, &mut skipped, || {
        super::update_config_tests::run(&["auto-exposure".into(), "--cameras".into(), "1".into()])
    });

    // ── Summary ──────────────────────────────────────────────────────────
    let elapsed = suite_start.elapsed().as_secs_f64();
    tracing::info!("");
    tracing::info!("╔══════════════════════════════════════════════════════════════╗");
    tracing::info!("║           TEST SUITE COMPLETE                                ║");
    tracing::info!("╠══════════════════════════════════════════════════════════════╣");
    tracing::info!("║  Duration:  {elapsed:.1}s{:50}║", "");
    tracing::info!("║  Passed:    {:<50}║", passed.len());
    tracing::info!("║  Failed:    {:<50}║", failed.len());
    tracing::info!("║  Skipped:   {:<50}║", skipped.len());
    tracing::info!("╠══════════════════════════════════════════════════════════════╣");

    if !passed.is_empty() {
        tracing::info!("║  ✓ PASSED:");
        for name in &passed {
            tracing::info!("║    - {name}");
        }
    }
    if !failed.is_empty() {
        tracing::info!("║  ✗ FAILED:");
        for name in &failed {
            tracing::info!("║    - {name}");
        }
    }
    if !skipped.is_empty() {
        tracing::info!("║  ⏭  SKIPPED:");
        for name in &skipped {
            tracing::info!("║    - {name}");
        }
    }
    tracing::info!("╚══════════════════════════════════════════════════════════════╝");
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
    _display_args: &[String],
    passed: &mut Vec<String>,
    failed: &mut Vec<String>,
    _skipped: &mut Vec<String>,
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
