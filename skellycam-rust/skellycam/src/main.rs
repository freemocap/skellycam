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

use skellycam::camera::{self, enumerate_directshow_cameras, CameraEvent, CameraIdentity};
use skellycam::camera_group::{CameraGroup, CameraGroupConfig};
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

    if args.iter().any(|arg| arg == "--detect") {
        return run_detection();
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
                    .map(|f| f.grab_timestamp_nanoseconds)
                    .unwrap_or(0);

                for (idx, frame) in payload.frames.iter().enumerate() {
                    if let (Some(recorder), Some(csv_writer)) =
                        (recorders.get_mut(idx), csv_writers.get_mut(idx))
                    {
                        let rgb_data = frame.data.as_bytes();
                        recorder.feed_frame(
                            rgb_data,
                            frame.frame_number,
                            frame.grab_timestamp_nanoseconds,
                            frame_ts,
                        )?;
                        csv_writer.write_row(
                            frame.frame_number,
                            frame.grab_timestamp_nanoseconds,
                            frame_ts,
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
                total_spread_ns += payload.inter_camera_grab_spread_nanoseconds() as f64;

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
    let index: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    let requested_width: u32 = 1280;
    let requested_height: u32 = 720;

    let cameras = enumerate_directshow_cameras().unwrap_or_default();
    let identity = cameras.iter()
        .find(|c| c.camera_index == index as i32)
        .cloned()
        .unwrap_or_else(|| CameraIdentity {
            display_name: format!("Camera {index}"),
            camera_index: index as i32,
            unique_identifier: format!("{:06x}", index),
            device_path: String::new(),
        });

    println!("Camera {index}: {} at {requested_width}x{requested_height}", identity.label());
    let barrier = Arc::new(BreakableBarrier::new(1));
    let (handle, event_receiver, frame_receiver) =
        camera::spawn_camera_thread(index, requested_width, requested_height, identity, barrier);

    let running = Arc::new(AtomicBool::new(true));
    let running_flag = running.clone();
    let _ = ctrlc::set_handler(move || {
        eprintln!("\nCtrl+C received, shutting down...");
        running_flag.store(false, Ordering::SeqCst);
    });

    let mut start: Option<Instant> = None;
    let mut frame_count: u64 = 0;
    let mut last_report = Instant::now();

    loop {
        if !running.load(Ordering::SeqCst) {
            eprintln!("Shutdown requested, exiting loop.");
            break;
        }

        while let Ok(event) = event_receiver.try_recv() {
            match event {
                CameraEvent::Error(message) => eprintln!("ERROR: {message}"),
            }
        }

        match frame_receiver.recv_timeout(Duration::from_millis(100)) {
            Ok(packet) => {
                if start.is_none() {
                    start = Some(Instant::now());
                    last_report = Instant::now();
                }
                frame_count += 1;

                if frame_count <= 3 {
                    println!(
                        "Frame {}: {}x{} ({} KB)",
                        packet.frame_number,
                        packet.width,
                        packet.height,
                        packet.data.len() / 1024,
                    );
                }

                if frame_count % 30 == 0 {
                    let elapsed = last_report.elapsed();
                    let fps = 30.0_f64 / elapsed.as_secs_f64();
                    println!(
                        "Frame {:>5} | {:>5.1} fps | {}x{}",
                        packet.frame_number, fps, packet.width, packet.height,
                    );
                    last_report = Instant::now();
                }

                if frame_count >= 500 {
                    println!("\nReached 500 frames, stopping.");
                    break;
                }
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => continue,
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                eprintln!("Camera channel disconnected.");
                break;
            }
        }
    }

    if let Some(s) = start {
        let total = s.elapsed();
        println!(
            "\n{frame_count} frames in {:.1}s ({:.1} fps avg).",
            total.as_secs_f64(),
            frame_count as f64 / total.as_secs_f64(),
        );
    }
    eprintln!("Shutting down camera...");
    drop(handle);
    eprintln!("Done.");
    Ok(())
}
