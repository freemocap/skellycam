//! SkellyCam Rust — camera test harness.
//!
//! IMPORTANT: Always use `cargo run --release` for real performance testing.
//!
//! Usage:
//!   cargo run --release -- --detect              # enumerate cameras
//!   cargo run --release                          # single-camera test (index 0)
//!   cargo run --release -- --cameras 2           # multi-camera lockstep (first 2)
//!   cargo run --release -- --cameras 6           # all 6 cameras
//!   cargo run --release -- --indices 0,2,4       # specific camera indices
//!   cargo run --release -- --record 2 --open     # record 2 cameras + open output folder

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use skellycam::api::AppState;
use skellycam::api::build_router;
use skellycam::camera::{self, enumerate_directshow_cameras, CameraEvent, CameraIdentity};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
use skellycam::camera_group_manager::CameraGroupManager;
use skellycam::recording::{finalize_recording, VideoRecorder};
use skellycam::sync_utils::BreakableBarrier;
use skellycam::timestamps::CsvWriter;

fn main() -> anyhow::Result<()> {
    if cfg!(debug_assertions) {
        eprintln!(
            "WARNING: Running in debug mode. Use `cargo run --release` for full performance.\n"
        );
    }
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("skellycam=info")),
        )
        .init();

    let args: Vec<String> = std::env::args().collect();

    // --serve: Start HTTP/WebSocket server with test page
    if args.iter().any(|arg| arg == "--serve") {
        return run_server();
    }

    if args.iter().any(|arg| arg == "--detect") {
        return run_detection();
    }

    // --manager N: test CameraGroupManager lifecycle with N cameras (defaults to all)
    if let Some(manager_pos) = args.iter().position(|arg| arg == "--manager") {
        let camera_count = args.get(manager_pos + 1)
            .and_then(|s| s.parse::<u32>().ok());
        return run_manager_test(camera_count);
    }

    // --record N: record N cameras for a fixed duration
    if let Some(record_count) = args.iter()
        .position(|arg| arg == "--record")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok())
    {
        let open_folder = args.iter().any(|arg| arg == "--open");
        return run_recording(record_count, open_folder);
    }

    let camera_count = args.iter()
        .position(|arg| arg == "--cameras")
        .and_then(|pos| args.get(pos + 1))
        .and_then(|s| s.parse::<u32>().ok());

    let explicit_indices: Option<Vec<u32>> = args.iter()
        .position(|arg| arg == "--indices")
        .and_then(|pos| args.get(pos + 1))
        .map(|s| s.split(',').filter_map(|n| n.trim().parse().ok()).collect());

    if camera_count.is_some() || explicit_indices.is_some() {
        return run_multi_camera(camera_count, explicit_indices);
    }

    run_single_camera()
}

fn run_detection() -> anyhow::Result<()> {
    let cameras = enumerate_directshow_cameras()?;
    if cameras.is_empty() {
        eprintln!("No cameras found.");
    } else {
        eprintln!(
            "Found {} camera{} total.",
            cameras.len(),
            if cameras.len() == 1 { "" } else { "s" }
        );
    }
    Ok(())
}

fn run_manager_test(requested_count: Option<u32>) -> anyhow::Result<()> {
    let all_cameras = enumerate_directshow_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let camera_count = match requested_count {
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

    eprintln!("══════════════════════════════════════════════════");
    eprintln!("  CAMERA GROUP MANAGER TEST — {} camera{}", camera_count, if camera_count == 1 { "" } else { "s" });
    eprintln!("══════════════════════════════════════════════════\n");

    let mut manager = CameraGroupManager::new();

    let configs: Vec<CameraGroupConfig> = all_cameras.iter()
        .take(camera_count)
        .map(|identity| CameraGroupConfig {
            camera_index: identity.camera_index as u32,
            requested_width: 1280,
            requested_height: 720,
            identity: identity.clone(),
        })
        .collect();

    let group_id = manager.create_or_update_group(configs, None)?;
    eprintln!("  Created group: {group_id}");
    eprintln!("  Active groups: {:?}", manager.list_groups());
    eprintln!("  Group count: {}\n", manager.group_count());

    let state = manager.to_state_dict();
    let state_json = serde_json::to_string_pretty(&state)?;
    eprintln!("  ── Manager State ──\n{state_json}\n");

    let group = manager.remove_group(&group_id)
        .ok_or_else(|| anyhow::anyhow!("Group '{group_id}' not found after creation"))?;

    let running = Arc::new(AtomicBool::new(true));
    let running_consumer = running.clone();

    let consumer_handle = std::thread::spawn(move || {
        let mut count: u64 = 0;
        let mut first_frame_time: Option<Instant> = None;
        let mut last_frame_time: Option<Instant> = None;
        while running_consumer.load(Ordering::SeqCst) {
            match group.multi_frame_receiver.recv_timeout(Duration::from_millis(100)) {
                Ok(_) => {
                    let now = Instant::now();
                    if first_frame_time.is_none() {
                        first_frame_time = Some(now);
                    }
                    last_frame_time = Some(now);
                    count += 1;
                }
                Err(std::sync::mpsc::RecvTimeoutError::Timeout) => continue,
                Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
            }
        }
        (group, count, first_frame_time, last_frame_time)
    });

    let run_duration_seconds = 5;
    eprintln!("  Running for {run_duration_seconds} seconds...\n");
    std::thread::sleep(Duration::from_secs(run_duration_seconds));
    running.store(false, Ordering::SeqCst);

    let (group, frame_count, first_frame_time, last_frame_time) = consumer_handle.join().unwrap();

    eprintln!();
    eprintln!("  ── Results ──");
    eprintln!("  Multiframes received: {frame_count}");
    eprintln!("  Cameras in group: {camera_count}");
    if let (Some(first), Some(last)) = (first_frame_time, last_frame_time) {
        let capture_duration = last.duration_since(first);
        if frame_count > 1 {
            let intervals = frame_count - 1;
            let fps = intervals as f64 / capture_duration.as_secs_f64();
            eprintln!("  Capture duration: {:.3} seconds (first frame to last frame)", capture_duration.as_secs_f64());
            eprintln!("  Multiframe rate: {fps:.1} fps (from {} inter-frame intervals)", intervals);
        }
    }

    eprintln!("\n  Shutting down...");
    group.shutdown();
    group.wait_for_shutdown();

    eprintln!("  Shutdown complete.");
    eprintln!("══════════════════════════════════════════════════\n");
    Ok(())
}

fn run_recording(camera_count: u32, open_folder: bool) -> anyhow::Result<()> {
    let all_cameras = enumerate_directshow_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let indices: Vec<u32> = (0..camera_count).collect();
    let configs: Vec<CameraGroupConfig> = indices.iter().map(|&index| {
        let identity = all_cameras.iter()
            .find(|c| c.camera_index == index as i32)
            .cloned()
            .unwrap_or_else(|| CameraIdentity {
                display_name: format!("Camera {index}"),
                camera_index: index as i32,
                unique_identifier: format!("{:06x}", index),
                device_path: String::new(),
            });
        CameraGroupConfig {
            camera_index: index,
            requested_width: 1280,
            requested_height: 720,
            identity,
        }
    }).collect();

    let num_cameras = configs.len();
    eprintln!("\n  ── Recording {num_cameras} camera(s) ──\n");

    let output_dir = {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let dir = PathBuf::from(format!("recordings_{timestamp}"));
        std::fs::create_dir_all(&dir)?;
        dir
    };

    let group = CameraGroup::create(configs)?;

    // Create one VideoRecorder + CsvWriter per camera
    let mut recorders: Vec<VideoRecorder> = Vec::with_capacity(num_cameras);
    let mut csv_writers: Vec<CsvWriter> = Vec::with_capacity(num_cameras);
    let mut video_paths: Vec<PathBuf> = Vec::with_capacity(num_cameras);
    let mut csv_paths: Vec<PathBuf> = Vec::with_capacity(num_cameras);

    for handle in &group.camera_handles {
        let base = format!(
            "camera_{}_{}",
            handle.identity.camera_index,
            handle.identity.unique_identifier,
        );
        let video_path = output_dir.join(format!("{base}.mp4"));
        let csv_path = output_dir.join(format!("{base}_timestamps.csv"));

        let recorder = VideoRecorder::new(
            video_path.clone(),
            &handle.identity,
            handle.width,
            handle.height,
            30.0,
        )?;
        let csv_writer = CsvWriter::new(csv_path.clone())?;

        recorders.push(recorder);
        csv_writers.push(csv_writer);
        video_paths.push(video_path);
        csv_paths.push(csv_path);
    }

    eprintln!("  Writing to: {}\n", output_dir.display());

    let running = Arc::new(AtomicBool::new(true));
    let running_flag = running.clone();
    let _ = ctrlc::set_handler(move || {
        eprintln!("\nCtrl+C received, stopping recording...");
        running_flag.store(false, Ordering::SeqCst);
    });

    let mut capture_start: Option<Instant> = None;
    let max_duration = Duration::from_secs(5);
    let mut multiframe_count: u64 = 0;

    loop {
        if !running.load(Ordering::SeqCst) {
            break;
        }
        if let Some(ref start) = capture_start {
            if start.elapsed() >= max_duration {
                break;
            }
        }

        match group.multi_frame_receiver.recv_timeout(Duration::from_millis(500)) {
            Ok(payload) => {
                if capture_start.is_none() {
                    capture_start = Some(Instant::now());
                    eprintln!("  (first frame received, starting {}s recording timer)\n", max_duration.as_secs());
                }

                let frame_ts = payload.frames.first()
                    .map(|f| f.timestamps.pre_capture_ns)
                    .unwrap_or(0);

                for (idx, frame) in payload.frames.iter().enumerate() {
                    if let (Some(recorder), Some(csv_writer)) =
                        (recorders.get_mut(idx), csv_writers.get_mut(idx))
                    {
                        let rgb_data = frame.data.as_bytes();
                        recorder.feed_frame(
                            rgb_data,
                            frame.frame_number,
                            frame.timestamps.pre_capture_ns,
                            frame_ts,
                        )?;
                        csv_writer.write_row(
                            frame.frame_number,
                            &frame.timestamps,
                        )?;
                    }
                }

                if multiframe_count > 0 && multiframe_count % 30 == 0 {
                    let elapsed = capture_start.as_ref().unwrap().elapsed().as_secs_f64();
                    eprintln!(
                        "  frame {multiframe_count:>5} | {elapsed:.1}s capture | ~{:.0}fps",
                        multiframe_count as f64 / elapsed,
                    );
                }
                multiframe_count += 1;
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => continue,
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                eprintln!("  Gatherer disconnected.");
                break;
            }
        }
    }

    let elapsed = capture_start.as_ref()
        .map(|s| s.elapsed().as_secs_f64())
        .unwrap_or(0.0);
    let capture_fps = if elapsed > 0.0 { multiframe_count as f64 / elapsed } else { 0.0 };
    eprintln!(
        "\n  Recording complete: {multiframe_count} multiframes in {elapsed:.1}s ({capture_fps:.1} fps capture)\n"
    );

    // Collect camera metadata BEFORE wait_for_shutdown consumes group
    let camera_infos: Vec<(CameraIdentity, u32, u32)> = group.camera_handles.iter().map(|h| {
        (h.identity.clone(), h.width, h.height)
    }).collect();

    eprintln!("  Shutting down...");
    group.shutdown();
    group.wait_for_shutdown();

    // Finalize all recorders and CSV writers
    let mut frame_counts: Vec<u64> = Vec::new();
    for recorder in recorders {
        let timestamps = recorder.finish()?;
        frame_counts.push(timestamps.len() as u64);
    }
    for csv_writer in csv_writers {
        let _ = csv_writer.finish()?;
    }

    let summary = finalize_recording(&output_dir, &camera_infos, &video_paths, &csv_paths)?;

    eprintln!("\n  ── Recording Summary ──");
    eprintln!("  Directory:       {}", output_dir.display());
    eprintln!("  Cameras:         {}", summary.csv_paths.len());
    eprintln!("  Frames/camera:   {}", summary.total_frames_per_camera);
    eprintln!("  Info JSON:       {}", summary.info_json_path.display());
    eprintln!("  Files:");
    for (idx, (video, csv)) in summary.video_paths.iter().zip(summary.csv_paths.iter()).enumerate() {
        eprintln!("    [{idx}] {}  /  {}", video.display(), csv.display());
    }
    if open_folder {
        eprintln!("  Opening folder...");
        let _ = std::process::Command::new("explorer")
            .arg(&output_dir)
            .spawn();
    }
    eprintln!();
    eprintln!("Done.");
    Ok(())
}

fn run_multi_camera(
    camera_count: Option<u32>,
    explicit_indices: Option<Vec<u32>>,
) -> anyhow::Result<()> {
    let all_cameras = enumerate_directshow_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected");
    }

    let indices: Vec<u32> = if let Some(explicit) = explicit_indices {
        explicit
    } else {
        let count = camera_count.unwrap_or(2) as usize;
        all_cameras.iter()
            .take(count)
            .map(|c| c.camera_index as u32)
            .collect()
    };

    let configs: Vec<CameraGroupConfig> = indices.iter().map(|&index| {
        let identity = all_cameras.iter()
            .find(|c| c.camera_index == index as i32)
            .cloned()
            .unwrap_or_else(|| CameraIdentity {
                display_name: format!("Camera {index}"),
                camera_index: index as i32,
                unique_identifier: format!("{:06x}", index),
                device_path: String::new(),
            });
        CameraGroupConfig {
            camera_index: index,
            requested_width: 1280,
            requested_height: 720,
            identity,
        }
    }).collect();

    let num_cameras = configs.len();
    eprintln!("\n  ── {num_cameras}-camera lockstep ── 600 multiframes (~20s) ──\n");

    let group = CameraGroup::create(configs)?;

    let running = Arc::new(AtomicBool::new(true));
    let running_flag = running.clone();
    let _ = ctrlc::set_handler(move || {
        eprintln!("\nCtrl+C received, shutting down...");
        running_flag.store(false, Ordering::SeqCst);
    });

    let start = Instant::now();
    let mut multiframe_count: u64 = 0;
    let mut total_spread_ns: f64 = 0.0;
    let max_multiframes: u64 = 600;

    loop {
        if !running.load(Ordering::SeqCst) {
            break;
        }

        match group.multi_frame_receiver.recv_timeout(Duration::from_millis(500)) {
            Ok(payload) => {
                multiframe_count += 1;
                total_spread_ns += payload.hardware_sync_spread_ns() as f64;

                if multiframe_count >= max_multiframes {
                    eprintln!("\n  Reached {max_multiframes} multiframes, stopping.");
                    break;
                }
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => continue,
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                eprintln!("  Gatherer disconnected.");
                break;
            }
        }
    }

    let elapsed = start.elapsed().as_secs_f64();
    let avg_spread_us = if multiframe_count > 0 {
        total_spread_ns / multiframe_count as f64 / 1_000.0
    } else {
        0.0
    };

    eprintln!();
    eprintln!("══════════════════════════════════════════════════");
    eprintln!("  Multi-Camera Summary");
    eprintln!("──────────────────────────────────────────────────");
    eprintln!("  Cameras:          {num_cameras}");
    eprintln!("  Multiframes:      {multiframe_count}");
    eprintln!("  Elapsed:          {elapsed:.1}s");
    if elapsed > 0.0 {
        eprintln!("  Multiframe rate:  {:.1} fps", multiframe_count as f64 / elapsed);
    }
    eprintln!("  Avg spread:       {avg_spread_us:.0} µs");
    eprintln!("══════════════════════════════════════════════════");
    eprintln!();

    eprintln!("Shutting down...");
    group.shutdown();
    group.wait_for_shutdown();
    eprintln!("Done.");
    Ok(())
}

fn run_single_camera() -> anyhow::Result<()> {
    // Single-camera mode uses CameraGroup with one camera — same barrier,
    // same gatherer, same pipeline as multi-camera. The degenerate case
    // should exercise the identical code path.
    run_multi_camera(Some(1), None)
}

fn run_server() -> anyhow::Result<()> {
    let state = Arc::new(AppState::new());
    let router = build_router(state.clone());

    let addr = "0.0.0.0:53117";
    eprintln!("══════════════════════════════════════════════════");
    eprintln!("  Skellycam Server");
    eprintln!("  http://localhost:53117");
    eprintln!("  Swagger docs: http://localhost:53117/docs");
    eprintln!("  Test page:    http://localhost:53117/test");
    eprintln!("  Press Ctrl+C to stop");
    eprintln!("══════════════════════════════════════════════════");

    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .enable_all()
        .build()?;

    rt.block_on(async {
        let listener = tokio::net::TcpListener::bind(addr).await?;

        axum::serve(listener, router)
            .with_graceful_shutdown(async {
                let _ = tokio::signal::ctrl_c().await;
                eprintln!("\nShutting down...");
            })
            .await?;

        Ok::<_, anyhow::Error>(())
    })?;

    // Clean shutdown: stop relay thread, close cameras
    state.running.store(false, Ordering::SeqCst);
    if let Some(handle) = state.relay_thread.blocking_lock().take() {
        let _ = handle.join();
    }

    eprintln!("Server stopped.");
    Ok(())
}
