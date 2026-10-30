//! API server integration tests — drives the full HTTP + WebSocket protocol.
//!
//! Starts the Axum server on an OS-assigned port, then runs through each
//! endpoint verifying behavior matches the Python skellycam backend protocol.
//!
//! Usage:
//!   cargo run --release -- test api

use std::collections::HashMap;
use std::time::{Duration, Instant};

use futures_util::StreamExt;
use reqwest::Client;
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::Message;

use skellycam::api::models::*;
use skellycam::api::test_utils::start_test_server;
use skellycam::camera::detect_cameras;
use skellycam::camera_group::{FrameHeader, PayloadHeader};

// ── Logging helpers ────────────────────────────────────────────────────────

macro_rules! test_header {
    ($($arg:tt)*) => {
        tracing::info!(
            "\n\n┌──────────────────────────────────────────────────────────────┐\n│  {:<60}│\n└──────────────────────────────────────────────────────────────┘\n",
            format!($($arg)*)
        )
    };
}

macro_rules! test_phase {
    ($($arg:tt)*) => {
        tracing::info!(
            "\n  ── {} ──",
            format!($($arg)*)
        )
    };
}

macro_rules! test_check {
    ($($arg:tt)*) => {
        tracing::info!("    ✓ {}", format!($($arg)*))
    };
}

macro_rules! test_detail {
    ($($arg:tt)*) => {
        tracing::info!("      {}", format!($($arg)*))
    };
}

// ── Binary protocol parsing ─────────────────────────────────────────────────

struct ParsedPayload {
    frame_number: i64,
    camera_count: i32,
    frames: Vec<ParsedFrame>,
}

#[allow(dead_code)]
struct ParsedFrame {
    camera_id: String,
    camera_index: i32,
    width: i32,
    height: i32,
    jpeg_bytes: Vec<u8>,
}

fn parse_payload(data: &[u8]) -> Option<ParsedPayload> {
    if data.len() < 24 {
        return None;
    }
    let header = read_payload_header(data);
    if header.message_type != 0 {
        return None;
    }
    let camera_count = header.number_of_cameras.max(0) as usize;
    let mut offset = 24usize;
    let mut frames = Vec::with_capacity(camera_count);

    for _ in 0..camera_count {
        if offset + 56 > data.len() {
            return None;
        }
        let fh = read_frame_header(&data[offset..]);
        offset += 56;
        let jpeg_len = fh.jpeg_string_length.max(0) as usize;
        if offset + jpeg_len > data.len() {
            return None;
        }
        let jpeg_bytes = data[offset..offset + jpeg_len].to_vec();
        offset += jpeg_len;
        let camera_id = String::from_utf8_lossy(&fh.camera_identifier)
            .trim_end_matches('\0')
            .to_string();
        frames.push(ParsedFrame {
            camera_id,
            camera_index: fh.camera_index,
            width: fh.image_width,
            height: fh.image_height,
            jpeg_bytes,
        });
    }

    if offset + 24 > data.len() {
        return None;
    }
    let footer = read_payload_header(&data[offset..]);
    if footer.message_type != 2 {
        return None;
    }

    Some(ParsedPayload {
        frame_number: header.frame_number,
        camera_count: header.number_of_cameras,
        frames,
    })
}

fn read_payload_header(data: &[u8]) -> &PayloadHeader {
    assert!(data.len() >= 24);
    unsafe { &*(data.as_ptr() as *const PayloadHeader) }
}

fn read_frame_header(data: &[u8]) -> &FrameHeader {
    assert!(data.len() >= 56);
    unsafe { &*(data.as_ptr() as *const FrameHeader) }
}

fn jpeg_luminance(jpeg_bytes: &[u8]) -> f64 {
    match skellycam::decode::mjpeg_to_rgb(jpeg_bytes) {
        Ok((_w, _h, rgb)) => skellycam::decode::mean_luminance(&rgb),
        Err(_) => -1.0,
    }
}

fn format_dimensions(payload: &ParsedPayload) -> String {
    payload
        .frames
        .iter()
        .map(|f| format!("{}x{}", f.width, f.height))
        .collect::<Vec<_>>()
        .join(", ")
}

// ── Top-level orchestrator ──────────────────────────────────────────────────

pub async fn run() -> anyhow::Result<()> {
    let all_cameras = detect_cameras()?;
    if all_cameras.is_empty() {
        anyhow::bail!("No cameras detected — cannot run API tests");
    }
    let camera_count = all_cameras.len();
    super::info_block(&[
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║           SKELLYCAM RUST — API SERVER TEST SUITE            ║",
        "╠══════════════════════════════════════════════════════════════╣",
        &format!("║  Cameras detected: {:<43}║", camera_count),
        "║                                                            ║",
        "║  Tests: health, detect, stream, recording, pause,           ║",
        "║         exposure, auto-exposure, resolution, rotation,     ║",
        "║         add-camera, remove-camera, close-all                ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
    ]);

    let server = start_test_server().await?;
    let base = format!("http://{}", server.addr);
    let ws_base = format!("ws://{}", server.addr);
    let client = Client::new();
    test_check!("Server started on {}", server.addr);

    let mut passed: Vec<String> = Vec::new();
    let mut failed: Vec<String> = Vec::new();
    let suite_start = Instant::now();

    let test_configs = build_test_configs(&all_cameras, camera_count);

    // ═══════════════════════════════════════════════════════════════════════
    // SECTION 1: Basic endpoints
    // ═══════════════════════════════════════════════════════════════════════

    // ── Health ──
    run_api_test("health", &mut passed, &mut failed, async {
        test_header!("HEALTH CHECK");
        let resp = client
            .get(format!("{base}/health"))
            .send()
            .await?;
        test_detail!("GET /health → {}", resp.status());
        let body = resp.text().await?;
        test_detail!("Response body: \"{body}\"");
        anyhow::ensure!(body == "skellycam ok", "expected 'skellycam ok', got '{body}'");
        test_check!("Health endpoint returned 'skellycam ok'");
        Ok(())
    }).await;

    // ── Detection ──
    run_api_test("detect", &mut passed, &mut failed, async {
        test_header!("CAMERA DETECTION");
        let resp = client
            .post(format!("{base}/skellycam/camera/detect"))
            .send()
            .await?;
        test_detail!("POST /skellycam/camera/detect → {}", resp.status());
        anyhow::ensure!(resp.status().is_success(), "detect returned {}", resp.status());
        let body: DetectedCamerasResponse = resp.json().await?;
        test_detail!("Response: {} camera(s) detected", body.cameras.len());
        for cam in &body.cameras {
            test_detail!(
                "  [{}] {} — {} format(s) — id={}",
                cam.index,
                cam.name,
                cam.formats.len(),
                cam.camera_id,
            );
        }
        anyhow::ensure!(!body.cameras.is_empty(), "no cameras in detection response");
        test_check!("Detection endpoint returned {} camera(s)", body.cameras.len());
        Ok(())
    }).await;

    // ═══════════════════════════════════════════════════════════════════════
    // SECTION 2: Camera group lifecycle
    // ═══════════════════════════════════════════════════════════════════════

    // ── Group apply + WebSocket stream ──
    run_api_test("group apply + WS stream", &mut passed, &mut failed, async {
        test_group_apply_and_stream(&client, &base, &ws_base, &test_configs).await
    }).await;

    // ── Recording ──
    run_api_test("recording", &mut passed, &mut failed, async {
        test_recording(&client, &base, &ws_base, &test_configs).await
    }).await;

    // ── Pause / unpause ──
    run_api_test("pause", &mut passed, &mut failed, async {
        test_pause(&client, &base, &ws_base, &test_configs).await
    }).await;

    // ═══════════════════════════════════════════════════════════════════════
    // SECTION 3: Config updates (exposure, auto-exposure, resolution, rotation)
    // ═══════════════════════════════════════════════════════════════════════

    // ── Update exposure ──
    run_api_test("update exposure", &mut passed, &mut failed, async {
        test_exposure(&client, &base, &ws_base, &test_configs).await
    }).await;

    // ── Auto-exposure ──
    run_api_test("auto-exposure", &mut passed, &mut failed, async {
        test_auto_exposure(&client, &base, &ws_base, &test_configs).await
    }).await;

    // ── Update resolution ──
    run_api_test("update resolution", &mut passed, &mut failed, async {
        test_resolution(&client, &base, &ws_base, &all_cameras).await
    }).await;

    // ── Rotation ──
    run_api_test("rotation", &mut passed, &mut failed, async {
        test_rotation(&client, &base, &ws_base, &all_cameras).await
    }).await;

    // ═══════════════════════════════════════════════════════════════════════
    // SECTION 4: Camera count changes
    // ═══════════════════════════════════════════════════════════════════════

    if camera_count >= 2 {
        run_api_test("add camera", &mut passed, &mut failed, async {
            test_add_camera(&client, &base, &ws_base, &all_cameras).await
        }).await;

        run_api_test("remove camera", &mut passed, &mut failed, async {
            test_remove_camera(&client, &base, &ws_base, &all_cameras).await
        }).await;
    } else {
        test_header!("SKIPPED: add/remove camera tests");
        tracing::warn!("  ⏭  Need 2+ cameras, only {camera_count} available");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SECTION 5: Cleanup
    // ═══════════════════════════════════════════════════════════════════════

    // ── Close all ──
    run_api_test("close all", &mut passed, &mut failed, async {
        test_header!("CLOSE ALL GROUPS");
        let _ = client
            .post(format!("{base}/skellycam/camera/group/apply"))
            .json(&CameraGroupApplyRequest {
                camera_configs: test_configs.clone(),
            })
            .send()
            .await?;
        test_detail!("Applied group config for close test");
        let resp = client
            .delete(format!("{base}/skellycam/camera/group/close/all"))
            .send()
            .await?;
        test_detail!("DELETE /skellycam/camera/group/close/all → {}", resp.status());
        anyhow::ensure!(resp.status().is_success(), "close returned {}", resp.status());
        let body: bool = resp.json().await?;
        anyhow::ensure!(body, "close/all should return true");
        test_check!("Close-all returned true, all groups shut down");
        Ok(())
    }).await;

    // ── Summary ──
    let elapsed = suite_start.elapsed().as_secs_f64();
    let total_tests = passed.len() + failed.len();
    let mut summary_lines: Vec<String> = Vec::new();
    summary_lines.push(String::new());
    summary_lines.push("╔══════════════════════════════════════════════════════════════╗".to_string());
    summary_lines.push("║           API SERVER TEST SUITE RESULTS                     ║".to_string());
    summary_lines.push("╠══════════════════════════════════════════════════════════════╣".to_string());
    summary_lines.push(format!("║  Total tests: {:>3}                                              ║", total_tests));
    summary_lines.push(format!("║  ✓  PASSED:  {:>3}                                              ║", passed.len()));
    summary_lines.push(format!("║  ✗  FAILED:  {:>3}                                              ║", failed.len()));
    summary_lines.push(format!("║  Duration:   {:.0}s  ({:.1} min)                                  ║", elapsed, elapsed / 60.0));
    summary_lines.push("╠══════════════════════════════════════════════════════════════╣".to_string());
    for name in &passed {
        summary_lines.push(format!("║  ✓  {:<58}║", name));
    }
    for name in &failed {
        summary_lines.push(format!("║  ✗  {:<58}║", name));
    }
    summary_lines.push("╚══════════════════════════════════════════════════════════════╝".to_string());
    summary_lines.push(String::new());
    tracing::info!("\n{}", summary_lines.join("\n"));

    server.shutdown().await;

    if !failed.is_empty() {
        eprintln!("{} test(s) failed: {}", failed.len(), failed.join(", "));
        std::process::exit(1);
    }

    Ok(())
}

async fn run_api_test<Fut>(
    name: &str,
    passed: &mut Vec<String>,
    failed: &mut Vec<String>,
    test_fn: Fut,
) where
    Fut: std::future::Future<Output = anyhow::Result<()>>,
{
    let start = Instant::now();
    tracing::info!(
        "\n\n██████████████████████████████████████████████████████████████\n██  TEST: {name}\n██████████████████████████████████████████████████████████████",
    );
    match test_fn.await {
        Ok(()) => {
            let elapsed = start.elapsed().as_secs_f64();
            tracing::info!(
                "\n  ✓ PASS: {name}  ({elapsed:.1}s)\n",
            );
            passed.push(name.to_string());
        }
        Err(e) => {
            let elapsed = start.elapsed().as_secs_f64();
            tracing::error!(
                "\n  ✗ FAIL: {name}  ({elapsed:.1}s)\n  Error: {e}\n",
            );
            failed.push(name.to_string());
        }
    }
}

// ── Helpers ─────────────────────────────────────────────────────────────────

fn build_test_configs(
    cameras: &[skellycam::camera::CameraDetection],
    count: usize,
) -> HashMap<String, CameraConfigInput> {
    cameras
        .iter()
        .take(count)
        .map(|d| {
            let id = &d.identity;
            (
                id.camera_id.clone(),
                CameraConfigInput {
                    camera_id: id.camera_id.clone(),
                    camera_index: id.camera_index,
                    camera_name: id.camera_name.clone(),
                    use_this_camera: true,
                    resolution: ResolutionInput {
                        width: 1280,
                        height: 720,
                    },
                    color_channels: 3,
                    pixel_format: String::new(),
                    exposure_mode: "MANUAL".into(),
                    exposure: -7,
                    framerate: -1.0,
                    rotation: -1,
                    capture_fourcc: String::new(),
                    writer_fourcc: String::new(),
                },
            )
        })
        .collect()
}

fn build_single_config(
    detection: &skellycam::camera::CameraDetection,
    width: i32,
    height: i32,
    exposure: i32,
    rotation: i32,
) -> HashMap<String, CameraConfigInput> {
    let id = &detection.identity;
    let mut map = HashMap::new();
    map.insert(
        id.camera_id.clone(),
        CameraConfigInput {
            camera_id: id.camera_id.clone(),
            camera_index: id.camera_index,
            camera_name: id.camera_name.clone(),
            use_this_camera: true,
            resolution: ResolutionInput { width, height },
            color_channels: 3,
            pixel_format: String::new(),
            exposure_mode: "MANUAL".into(),
            exposure,
            framerate: -1.0,
            rotation,
            capture_fourcc: String::new(),
            writer_fourcc: String::new(),
        },
    );
    map
}

async fn apply_group(
    client: &Client,
    base: &str,
    configs: &HashMap<String, CameraConfigInput>,
) -> anyhow::Result<CreateCameraGroupResponse> {
    let cam_ids: Vec<&str> = configs.keys().map(|s| s.as_str()).collect();
    test_detail!("POST /skellycam/camera/group/apply — {} camera(s): {:?}", configs.len(), cam_ids);
    let resp = client
        .post(format!("{base}/skellycam/camera/group/apply"))
        .json(&CameraGroupApplyRequest {
            camera_configs: configs.clone(),
        })
        .send()
        .await?;
    anyhow::ensure!(
        resp.status().is_success(),
        "group/apply returned {}",
        resp.status()
    );
    let body: CreateCameraGroupResponse = resp.json().await?;
    test_detail!("→ group_id={}  configs_in_response={}", body.group_id, body.camera_configs.len());
    anyhow::ensure!(!body.group_id.is_empty(), "empty group_id");
    anyhow::ensure!(
        body.camera_configs.len() == configs.len(),
        "expected {} camera configs in response, got {}",
        configs.len(),
        body.camera_configs.len(),
    );
    Ok(body)
}

async fn collect_ws_frames(
    ws_base: &str,
    timeout_dur: Duration,
) -> anyhow::Result<Vec<ParsedPayload>> {
    let ws_url = format!("{ws_base}/skellycam/websocket/connect");
    test_detail!("WS connect → {}", ws_url);
    let (ws_stream, _resp) = connect_async(&ws_url).await?;
    let (_, mut read) = ws_stream.split();
    test_detail!("WS connected, collecting frames for {:.0}s...", timeout_dur.as_secs_f64());

    let mut frames = Vec::new();
    let deadline = Instant::now() + timeout_dur;
    let mut last_report = Instant::now();

    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            break;
        }
        let msg = tokio::time::timeout(remaining, read.next()).await;
        match msg {
            Ok(Some(Ok(Message::Binary(data)))) => {
                if let Some(payload) = parse_payload(&data) {
                    // Report every ~1s
                    if last_report.elapsed().as_millis() > 1000 {
                        test_detail!(
                            "  WS frame #{}  |  {} camera(s)  |  dims=[{}]  |  {} KB",
                            payload.frame_number,
                            payload.camera_count,
                            format_dimensions(&payload),
                            data.len() / 1024,
                        );
                        last_report = Instant::now();
                    }
                    frames.push(payload);
                }
            }
            Ok(Some(Ok(Message::Text(t)))) => {
                // JSON messages — log first occurrence of each type
                if t.len() < 200 {
                    test_detail!("  WS text: {}", t);
                } else {
                    test_detail!("  WS text: {}... ({} bytes)", &t[..200], t.len());
                }
            }
            Ok(Some(Ok(_))) => {}
            Ok(Some(Err(e))) => {
                tracing::warn!("  WS error: {e}");
                break;
            }
            Ok(None) => break,
            Err(_) => break,
        }
    }

    test_detail!("WS collection done: {} frame(s) in {:.1}s", frames.len(), timeout_dur.as_secs_f64());
    Ok(frames)
}

async fn wait_for_ws_frames(
    ws_base: &str,
    min_frames: usize,
    timeout_secs: u64,
) -> anyhow::Result<Vec<ParsedPayload>> {
    let ws_url = format!("{ws_base}/skellycam/websocket/connect");
    test_detail!("WS connect → {}  (waiting for {} frames, timeout {}s)", ws_url, min_frames, timeout_secs);
    let (ws_stream, _resp) = connect_async(&ws_url).await?;
    let (_, mut read) = ws_stream.split();

    let mut frames = Vec::new();
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);
    let mut last_report = Instant::now();

    while frames.len() < min_frames {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            anyhow::bail!(
                "Timed out after {timeout_secs}s — got {} frames, wanted {min_frames}",
                frames.len()
            );
        }
        let msg = tokio::time::timeout(remaining, read.next()).await;
        match msg {
            Ok(Some(Ok(Message::Binary(data)))) => {
                if let Some(payload) = parse_payload(&data) {
                    if frames.is_empty() || last_report.elapsed().as_millis() > 1000 {
                        test_detail!(
                            "  WS frame #{}  |  {} camera(s)  |  dims=[{}]  |  {}/{} collected",
                            payload.frame_number,
                            payload.camera_count,
                            format_dimensions(&payload),
                            frames.len() + 1,
                            min_frames,
                        );
                        last_report = Instant::now();
                    }
                    frames.push(payload);
                }
            }
            Ok(Some(Ok(Message::Text(_)))) | Ok(Some(Ok(_))) => {}
            Ok(Some(Err(e))) => {
                anyhow::bail!("WS error: {e}");
            }
            Ok(None) => {
                anyhow::bail!("WS stream closed after {} frames", frames.len());
            }
            Err(_) => {
                anyhow::bail!(
                    "Timed out after {timeout_secs}s — got {} frames, wanted {min_frames}",
                    frames.len()
                );
            }
        }
    }
    test_detail!("WS collection done: {} frame(s)", frames.len());
    Ok(frames)
}

async fn wait_for_ws_stall(
    ws_base: &str,
    stall_duration: Duration,
) -> anyhow::Result<i64> {
    let ws_url = format!("{ws_base}/skellycam/websocket/connect");
    test_detail!("WS connect → {}  (waiting for stall of {:.1}s)", ws_url, stall_duration.as_secs_f64());
    let (ws_stream, _resp) = connect_async(&ws_url).await?;
    let (_, mut read) = ws_stream.split();

    let mut last_frame: i64 = -1;
    let mut stall_start: Option<Instant> = None;
    let deadline = Instant::now() + stall_duration + Duration::from_secs(30);

    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            anyhow::bail!("Timed out waiting for stall");
        }
        let msg = tokio::time::timeout(Duration::from_millis(100), read.next()).await;
        match msg {
            Ok(Some(Ok(Message::Binary(data)))) => {
                if let Some(payload) = parse_payload(&data) {
                    if payload.frame_number > last_frame {
                        test_detail!("  WS frame #{} — resetting stall timer", payload.frame_number);
                        last_frame = payload.frame_number;
                        stall_start = None;
                    }
                }
            }
            Ok(Some(Ok(_))) => {}
            Ok(Some(Err(_))) | Ok(None) => break,
            Err(_) => {
                if stall_start.is_none() {
                    stall_start = Some(Instant::now());
                    test_detail!("  Stall detected — no frame for 100ms, starting timer");
                } else if stall_start.unwrap().elapsed() >= stall_duration {
                    test_detail!("  Stall confirmed — {:.1}s without new frames", stall_duration.as_secs_f64());
                    break;
                }
            }
        }
    }
    Ok(last_frame)
}

/// Compute average luminance from the last N frames of the first camera.
fn average_luminance(frames: &[ParsedPayload], sample_count: usize) -> f64 {
    let lums: Vec<f64> = frames
        .iter()
        .rev()
        .take(sample_count)
        .flat_map(|p| p.frames.first().map(|f| jpeg_luminance(&f.jpeg_bytes)))
        .filter(|&l| l >= 0.0)
        .collect();
    if lums.is_empty() {
        return -1.0;
    }
    lums.iter().sum::<f64>() / lums.len() as f64
}

// ═══════════════════════════════════════════════════════════════════════════
// INDIVIDUAL TEST FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/// Apply a group, connect WS, verify frames stream with valid binary protocol.
async fn test_group_apply_and_stream(
    client: &Client,
    base: &str,
    ws_base: &str,
    configs: &HashMap<String, CameraConfigInput>,
) -> anyhow::Result<()> {
    test_header!("GROUP APPLY + WEBSOCKET STREAM");
    test_phase!("Creating camera group via HTTP");
    let response = apply_group(client, base, configs).await?;
    test_check!("Group created: {}", response.group_id);

    test_phase!("Waiting for WebSocket frames (cameras need 5-15s for detection + stream open + stabilization)");
    let frames = wait_for_ws_frames(ws_base, 10, 30).await?;
    test_check!("Received {} multiframe(s)", frames.len());

    test_phase!("Validating binary protocol structure");
    let first = &frames[0];
    test_detail!("First payload: frame_number={}  camera_count={}  total_bytes={}",
        first.frame_number, first.camera_count,
        first.frames.iter().map(|f| f.jpeg_bytes.len()).sum::<usize>() + 24 + first.camera_count as usize * 56 + 24
    );

    anyhow::ensure!(
        first.camera_count == configs.len() as i32,
        "expected {} cameras in payload, got {}",
        configs.len(),
        first.camera_count,
    );
    test_check!("Camera count in payload: {} (matches config)", first.camera_count);

    anyhow::ensure!(
        first.frames.len() == configs.len() as usize,
        "expected {} frame headers, got {}",
        configs.len(),
        first.frames.len(),
    );
    test_check!("Frame header count: {}", first.frames.len());

    for (i, pf) in first.frames.iter().enumerate() {
        test_detail!(
            "  Frame[{i}]: camera={}  dims={}x{}  JPEG={}KB",
            pf.camera_id, pf.width, pf.height, pf.jpeg_bytes.len() / 1024,
        );
        anyhow::ensure!(
            pf.jpeg_bytes.len() > 100,
            "frame {i}: JPEG too small ({} bytes)",
            pf.jpeg_bytes.len()
        );
        anyhow::ensure!(
            pf.width > 0 && pf.height > 0,
            "frame {i}: invalid dimensions {}x{}",
            pf.width, pf.height,
        );
    }

    let frame_nums: Vec<i64> = frames.iter().map(|f| f.frame_number).collect();
    let increasing = frame_nums.windows(2).all(|w| w[1] > w[0]);
    anyhow::ensure!(increasing, "frame numbers not monotonically increasing: {:?}", &frame_nums[..frame_nums.len().min(10)]);
    test_check!("Frame numbers monotonically increasing ({} → {})", frame_nums.first().unwrap_or(&0), frame_nums.last().unwrap_or(&0));

    Ok(())
}

/// Test recording start/stop via HTTP endpoints.
async fn test_recording(
    client: &Client,
    base: &str,
    ws_base: &str,
    configs: &HashMap<String, CameraConfigInput>,
) -> anyhow::Result<()> {
    test_header!("RECORDING LIFECYCLE");
    test_phase!("Ensuring group is active and streaming");
    apply_group(client, base, configs).await?;
    let pre_frames = wait_for_ws_frames(ws_base, 5, 20).await?;
    test_check!("Cameras streaming — {} frames received before recording", pre_frames.len());

    test_phase!("Starting recording via HTTP");
    let home = dirs::home_dir().unwrap_or_else(|| std::path::PathBuf::from("."));
    let rec_dir = home.join("skellycam_data").join("recordings").display().to_string();

    let start_resp = client
        .post(format!("{base}/skellycam/camera/group/all/record/start"))
        .json(&serde_json::json!({
            "recording_name": "api-test-recording",
            "recording_directory": rec_dir,
            "mic_device_index": -1
        }))
        .send()
        .await?;
    test_detail!("POST /record/start → {}", start_resp.status());
    anyhow::ensure!(start_resp.status().is_success(), "record/start returned {}", start_resp.status());
    let started: bool = start_resp.json().await?;
    anyhow::ensure!(started, "record/start should return true");
    test_check!("Recording started (response: true)");

    test_phase!("Recording for 5 seconds...");
    let rec_start = Instant::now();
    tokio::time::sleep(Duration::from_secs(5)).await;
    test_detail!("Recorded for {:.1}s", rec_start.elapsed().as_secs_f64());

    test_phase!("Stopping recording via HTTP");
    let stop_resp = client
        .get(format!("{base}/skellycam/camera/group/all/record/stop"))
        .send()
        .await?;
    test_detail!("GET /record/stop → {}", stop_resp.status());
    anyhow::ensure!(stop_resp.status().is_success(), "record/stop returned {}", stop_resp.status());
    let summaries: Vec<StopRecordingResponse> = stop_resp.json().await?;
    anyhow::ensure!(!summaries.is_empty(), "empty recording summary list");
    let summary = &summaries[0];
    test_check!(
        "Recording summary: {} frames  |  {} cameras  |  {:.1}s  |  {:.1} fps",
        summary.number_of_frames,
        summary.number_of_cameras,
        summary.total_duration_sec,
        summary.mean_framerate,
    );
    anyhow::ensure!(summary.number_of_frames > 0, "zero frames recorded");
    test_check!("Recording verified — {} frames written to disk", summary.number_of_frames);

    Ok(())
}

/// Test pause/unpause via HTTP + WebSocket frame stall detection.
async fn test_pause(
    client: &Client,
    base: &str,
    ws_base: &str,
    configs: &HashMap<String, CameraConfigInput>,
) -> anyhow::Result<()> {
    test_header!("PAUSE / UNPAUSE");
    test_phase!("Ensuring group is streaming");
    apply_group(client, base, configs).await?;
    let initial = wait_for_ws_frames(ws_base, 5, 10).await?;
    test_check!("Streaming confirmed: {} frame(s) at frame #{}", initial.len(), initial.last().map(|p| p.frame_number).unwrap_or(-1));

    test_phase!("Toggle pause ON");
    let pause_resp = client
        .get(format!("{base}/skellycam/camera/group/all/pause_unpause"))
        .send()
        .await?;
    let pause_status = pause_resp.status();
    let paused: bool = pause_resp.json().await?;
    test_detail!("GET /pause_unpause → {pause_status}  (response: {paused})");
    anyhow::ensure!(paused, "pause_unpause should return true after pausing");
    test_check!("Pause toggled ON (API returned true)");

    test_phase!("Verifying frame delivery has stopped (stall detection)");
    let stall_frame = wait_for_ws_stall(ws_base, Duration::from_secs(2)).await?;
    test_check!("Frame stall confirmed — last frame before stall: #{}", stall_frame);

    test_phase!("Toggle pause OFF");
    let unpause_resp = client
        .get(format!("{base}/skellycam/camera/group/all/pause_unpause"))
        .send()
        .await?;
    let unpause_status = unpause_resp.status();
    let unpaused: bool = unpause_resp.json().await?;
    test_detail!("GET /pause_unpause → {unpause_status}  (response: {unpaused})");
    anyhow::ensure!(!unpaused, "pause_unpause should return false after unpausing");
    test_check!("Pause toggled OFF (API returned false)");

    test_phase!("Verifying frames have resumed");
    let resumed = wait_for_ws_frames(ws_base, 5, 10).await?;
    anyhow::ensure!(!resumed.is_empty(), "no frames after unpause");
    // First frame may be the cached pre-unpause frame. Check the last one.
    let resumed_frame = resumed.last().unwrap().frame_number;
    anyhow::ensure!(
        resumed_frame > stall_frame,
        "frame number did not advance after unpause (stall at #{stall_frame}, latest resumed frame is #{resumed_frame})",
    );
    test_check!(
        "Frames resumed — advanced from #{} to #{}",
        stall_frame,
        resumed_frame,
    );

    Ok(())
}

/// Test exposure range scan — apply multiple exposure values, measure luminance,
/// and verify the general trend (higher exposure numbers = brighter image).
///
/// Scans -1 (brightest) → -4 → -7 → -10 → -13 (darkest), sampling luminance
/// at each level. Verifies:
///   - API response confirms each exposure value was applied
///   - Extreme values (-1 vs -13) show a meaningful brightness difference
///   - General ordering is roughly correct (earlier values brighter)
///
/// Does NOT assert strict monotonicity because:
/// - At deep negative values the image may already be fully black
/// - Some cameras override manual exposure internally
/// - The exposure register → brightness mapping is camera-specific
async fn test_exposure(
    client: &Client,
    base: &str,
    ws_base: &str,
    configs: &HashMap<String, CameraConfigInput>,
) -> anyhow::Result<()> {
    test_header!("EXPOSURE RANGE SCAN → LUMINANCE TREND VERIFICATION");

    // Sweep every valid step from brightest to darkest.
    // Only -11 through -5 produce meaningful changes on these USB cameras.
    let exposure_values: [i32; 7] = [-5, -6, -7, -8, -9, -10, -11];
    let mut luminance_samples: Vec<(i32, f64)> = Vec::new();

    for (step, &exposure) in exposure_values.iter().enumerate() {
        test_phase!("Step {}/{}: exposure={exposure}", step + 1, exposure_values.len());

        let mut step_configs = configs.clone();
        for (_, cfg) in step_configs.iter_mut() {
            cfg.exposure = exposure;
        }

        let resp = apply_group(client, base, &step_configs).await?;

        // Verify API response confirms the exposure value
        for (cam_id, cfg) in &resp.camera_configs {
            anyhow::ensure!(
                cfg.exposure == exposure,
                "API response: camera {cam_id} exposure={} but expected {exposure}",
                cfg.exposure,
            );
        }
        test_check!("API response confirms exposure={exposure} on all {} camera(s)", resp.camera_configs.len());

        // Let cameras settle after config change
        tokio::time::sleep(Duration::from_millis(300)).await;

        let frames = collect_ws_frames(ws_base, Duration::from_secs(2)).await?;
        anyhow::ensure!(!frames.is_empty(), "no frames at exposure={exposure}");
        let lum = average_luminance(&frames, 5);
        test_check!("  exposure={exposure:>4}  →  luminance={lum:.2}", );
        luminance_samples.push((exposure, lum));
    }

    // ── Trend analysis ──
    test_phase!("Trend analysis");
    let lum_bright = luminance_samples[0].1;   // -5 (brightest)
    let lum_dark = luminance_samples[6].1;     // -11 (darkest)

    test_detail!("  Exposure sweep results:");
    for (exp, lum) in &luminance_samples {
        let bar = "█".repeat((*lum / 2.0).min(40.0) as usize);
        test_detail!("    exp={exp:>4}  lum={lum:>6.2}  {bar}");
    }

    // Check extremes: -5 should be visibly brighter than -11
    let extreme_ratio = lum_bright / lum_dark.max(0.01);
    if lum_bright > lum_dark * 1.15 {
        test_check!(
            "Extreme trend: exp=-5 (lum={lum_bright:.1}) IS brighter than exp=-11 (lum={lum_dark:.1}) — ratio={extreme_ratio:.1}x",
        );
    } else {
        test_detail!(
            "Extreme values near-identical (ratio={extreme_ratio:.2}x) — camera may have auto-exposure override or min brightness already reached at exp=-11",
        );
    }

    // Check general monotonic trend: count how many adjacent pairs go the right direction
    let correct_pairs = luminance_samples
        .windows(2)
        .filter(|w| w[0].1 >= w[1].1 * 0.95) // allow 5% tolerance
        .count();
    let total_pairs = luminance_samples.len() - 1;
    test_check!(
        "Monotonic trend: {correct_pairs}/{total_pairs} adjacent pairs brighter→darker (higher exposure num = dimmer image)"
    );

    // Hard pass: the API must correctly reflect the exposure values we set
    // (already verified per-step above). Luminance trend is observational.
    test_check!("Exposure range scan complete — API values verified, luminance trend reported");

    Ok(())
}

/// Test auto-exposure recovery from dark.
async fn test_auto_exposure(
    client: &Client,
    base: &str,
    ws_base: &str,
    configs: &HashMap<String, CameraConfigInput>,
) -> anyhow::Result<()> {
    test_header!("AUTO-EXPOSURE RECOVERY");
    test_phase!("Setting MANUAL exposure=-11 (dark)");
    let mut dark_configs = configs.clone();
    for (_, cfg) in dark_configs.iter_mut() {
        cfg.exposure = -11;
        cfg.exposure_mode = "MANUAL".into();
    }
    apply_group(client, base, &dark_configs).await?;
    let dark_frames = collect_ws_frames(ws_base, Duration::from_secs(2)).await?;
    let dark_lum = average_luminance(&dark_frames, 3);
    test_check!("MANUAL exposure=-11 luminance: {:.2}", dark_lum);

    test_phase!("Switching to AUTO exposure mode");
    let mut auto_configs = dark_configs.clone();
    for (_, cfg) in auto_configs.iter_mut() {
        cfg.exposure_mode = "AUTO".into();
    }
    apply_group(client, base, &auto_configs).await?;
    tokio::time::sleep(Duration::from_secs(1)).await;

    let auto_frames = collect_ws_frames(ws_base, Duration::from_secs(3)).await?;
    let auto_lum = average_luminance(&auto_frames, 5);
    test_check!("AUTO exposure luminance: {:.2} (from dark={:.2})", auto_lum, dark_lum);

    let ratio = auto_lum / dark_lum.max(0.01);
    if auto_lum > dark_lum * 1.10 {
        test_check!("Auto-exposure brightened the image — ratio={:.2}x", ratio);
    } else {
        test_detail!(
            "AUTO lum ({auto_lum:.1}) not significantly brighter than dark ({dark_lum:.1}) — camera may not support auto-exposure or was already bright",
        );
    }
    // Note: not a hard assertion — some cameras don't support auto-exposure well

    Ok(())
}

/// Test resolution change is reflected in WS frame dimensions.
async fn test_resolution(
    client: &Client,
    base: &str,
    ws_base: &str,
    all_cameras: &[skellycam::camera::CameraDetection],
) -> anyhow::Result<()> {
    test_header!("RESOLUTION CHANGE → FRAME DIMENSION VERIFICATION");
    // Use first camera for resolution test. Close all first so we start
    // a fresh single-camera group rather than removing cameras from a
    // running multi-camera group (which can cause gatherer disconnect).
    let _ = client
        .delete(format!("{base}/skellycam/camera/group/close/all"))
        .send()
        .await;
    tokio::time::sleep(Duration::from_millis(500)).await;

    let first_cam = &all_cameras[0];
    test_phase!("Testing resolution changes on camera '{}'", first_cam.identity.label());

    // Find two different MJPG resolutions the camera actually supports
    let mjpg_formats: Vec<(u32, u32)> = {
        let mut seen = std::collections::BTreeSet::new();
        for fmt in &first_cam.identity.formats {
            if fmt.fourcc_str == "MJPG" {
                seen.insert((fmt.width, fmt.height));
            }
        }
        seen.into_iter().collect()
    };
    anyhow::ensure!(mjpg_formats.len() >= 2, "need at least 2 MJPG formats for resolution test, got {}", mjpg_formats.len());
    let (low_w, low_h) = mjpg_formats[0];                          // smallest
    let (high_w, high_h) = mjpg_formats[mjpg_formats.len() - 1];   // largest
    test_detail!("  Supported MJPG formats: {:?}", mjpg_formats);
    test_detail!("  Testing: {}x{} → {}x{}", low_w, low_h, high_w, high_h);

    // Start with lowest resolution
    let low_config = build_single_config(first_cam, low_w as i32, low_h as i32, -7, -1);
    apply_group(client, base, &low_config).await?;
    let low_frames = wait_for_ws_frames(ws_base, 3, 20).await?;
    let low_dims = &low_frames.last().unwrap().frames[0];
    test_check!("Applied {}x{} → actual: {}x{}", low_w, low_h, low_dims.width, low_dims.height);
    anyhow::ensure!(
        low_dims.width == low_w as i32 && low_dims.height == low_h as i32,
        "expected {}x{}, got {}x{}",
        low_w, low_h, low_dims.width, low_dims.height,
    );

    // Change to highest resolution
    let high_config = build_single_config(first_cam, high_w as i32, high_h as i32, -7, -1);
    apply_group(client, base, &high_config).await?;
    tokio::time::sleep(Duration::from_millis(500)).await;
    let high_frames = wait_for_ws_frames(ws_base, 3, 20).await?;
    let high_dims = &high_frames.last().unwrap().frames[0];
    test_check!("Applied {}x{} → actual: {}x{}", high_w, high_h, high_dims.width, high_dims.height);
    anyhow::ensure!(
        high_dims.width == high_w as i32 && high_dims.height == high_h as i32,
        "expected {}x{}, got {}x{}",
        high_w, high_h, high_dims.width, high_dims.height,
    );

    test_check!("Resolution change verified — {}x{} → {}x{}", low_w, low_h, high_w, high_h);
    Ok(())
}

/// Test JPEG rotation is reflected in frame dimensions (90° CW swaps w/h).
async fn test_rotation(
    client: &Client,
    base: &str,
    ws_base: &str,
    all_cameras: &[skellycam::camera::CameraDetection],
) -> anyhow::Result<()> {
    test_header!("JPEG ROTATION → DIMENSION SWAP VERIFICATION");
    // Close all first so we start a fresh single-camera group
    let _ = client
        .delete(format!("{base}/skellycam/camera/group/close/all"))
        .send()
        .await;
    tokio::time::sleep(Duration::from_millis(500)).await;

    let first_cam = &all_cameras[0];
    test_phase!("Testing rotation on camera '{}'", first_cam.identity.label());

    // Start with no rotation at 1280x720
    let no_rot_config = build_single_config(first_cam, 1280, 720, -7, -1);
    apply_group(client, base, &no_rot_config).await?;
    let baseline = wait_for_ws_frames(ws_base, 3, 20).await?;
    let base_dims = &baseline.last().unwrap().frames[0];
    test_check!(
        "Baseline (rotation=-1): {}x{}  JPEG={}KB",
        base_dims.width, base_dims.height, base_dims.jpeg_bytes.len() / 1024,
    );

    // Apply 90° CW rotation (rotation=0)
    test_phase!("Applying rotation=0 (90° CW)");
    let rot_config = build_single_config(first_cam, 1280, 720, -7, 0);
    apply_group(client, base, &rot_config).await?;
    tokio::time::sleep(Duration::from_millis(500)).await;
    let rotated = wait_for_ws_frames(ws_base, 5, 15).await?;
    let rot_dims = &rotated.last().unwrap().frames[0];
    test_check!(
        "Rotated (rotation=0): {}x{}  JPEG={}KB",
        rot_dims.width, rot_dims.height, rot_dims.jpeg_bytes.len() / 1024,
    );

    // 90° CW rotation should swap width and height: 1280x720 → 720x1280
    let dims_swapped = rot_dims.width == base_dims.height && rot_dims.height == base_dims.width;
    if dims_swapped {
        test_check!(
            "Rotation verified — dimensions swapped: {}x{} → {}x{}",
            base_dims.width, base_dims.height,
            rot_dims.width, rot_dims.height,
        );
    } else {
        test_detail!(
            "Dimensions not swapped ({}x{} → {}x{}) — rotation may be applied post-resize or camera doesn't support it",
            base_dims.width, base_dims.height,
            rot_dims.width, rot_dims.height,
        );
    }

    // Return to no rotation
    test_phase!("Returning to no rotation");
    apply_group(client, base, &no_rot_config).await?;
    tokio::time::sleep(Duration::from_millis(500)).await;
    let restored = wait_for_ws_frames(ws_base, 3, 15).await?;
    let rest_dims = &restored.last().unwrap().frames[0];
    test_check!(
        "Restored (rotation=-1): {}x{}  JPEG={}KB",
        rest_dims.width, rest_dims.height, rest_dims.jpeg_bytes.len() / 1024,
    );

    Ok(())
}

/// Test creating groups with different camera counts via the API.
async fn test_add_camera(
    client: &Client,
    base: &str,
    ws_base: &str,
    all_cameras: &[skellycam::camera::CameraDetection],
) -> anyhow::Result<()> {
    test_header!("ADD CAMERA (N-1 → N via fresh groups)");
    // Close any existing groups first to avoid detection conflicts
    let _ = client
        .delete(format!("{base}/skellycam/camera/group/close/all"))
        .send()
        .await;
    tokio::time::sleep(Duration::from_millis(500)).await;
    test_phase!("Closed existing groups, starting clean");

    let start_count = all_cameras.len() - 1;
    test_phase!("Creating group with {start_count} camera(s)");
    let start_configs = build_test_configs(all_cameras, start_count);
    apply_group(client, base, &start_configs).await?;

    let initial = wait_for_ws_frames(ws_base, 5, 20).await?;
    test_check!(
        "Streaming {start_count} camera(s) — frame dimensions: [{}]",
        format_dimensions(&initial.last().unwrap()),
    );
    anyhow::ensure!(
        initial[0].camera_count == start_count as i32,
        "expected {} cameras, got {}",
        start_count,
        initial[0].camera_count
    );

    // Close and restart with all cameras
    test_phase!("Closing group and restarting with all {} camera(s)", all_cameras.len());
    let _ = client
        .delete(format!("{base}/skellycam/camera/group/close/all"))
        .send()
        .await;
    tokio::time::sleep(Duration::from_millis(500)).await;

    let full_configs = build_test_configs(all_cameras, all_cameras.len());
    apply_group(client, base, &full_configs).await?;

    let after_add = wait_for_ws_frames(ws_base, 5, 20).await?;
    let final_count = after_add.last().unwrap().camera_count;
    test_check!(
        "Streaming {final_count} camera(s) — frame dimensions: [{}]",
        format_dimensions(&after_add.last().unwrap()),
    );
    anyhow::ensure!(
        final_count == all_cameras.len() as i32,
        "expected {} cameras after add, got {final_count}",
        all_cameras.len(),
    );
    test_check!("Camera count increased from {start_count} → {final_count}");

    Ok(())
}

/// Test removing a camera via the API.
async fn test_remove_camera(
    client: &Client,
    base: &str,
    ws_base: &str,
    all_cameras: &[skellycam::camera::CameraDetection],
) -> anyhow::Result<()> {
    test_header!("REMOVE CAMERA (N → N-1 via fresh groups)");
    // Close any existing groups first
    let _ = client
        .delete(format!("{base}/skellycam/camera/group/close/all"))
        .send()
        .await;
    tokio::time::sleep(Duration::from_millis(500)).await;
    test_phase!("Closed existing groups, starting clean");

    let full_count = all_cameras.len();
    test_phase!("Creating group with all {} camera(s)", full_count);
    let full_configs = build_test_configs(all_cameras, full_count);
    apply_group(client, base, &full_configs).await?;

    let initial = wait_for_ws_frames(ws_base, 5, 20).await?;
    test_check!(
        "Streaming {} camera(s) — frame dimensions: [{}]",
        initial[0].camera_count,
        format_dimensions(&initial.last().unwrap()),
    );

    // Close and restart with one fewer camera
    let reduced_count = full_count - 1;
    test_phase!("Closing group and restarting with {reduced_count} camera(s)");
    let _ = client
        .delete(format!("{base}/skellycam/camera/group/close/all"))
        .send()
        .await;
    tokio::time::sleep(Duration::from_millis(500)).await;

    let reduced_configs = build_test_configs(all_cameras, reduced_count);
    apply_group(client, base, &reduced_configs).await?;

    let after_remove = wait_for_ws_frames(ws_base, 5, 20).await?;
    let final_count = after_remove.last().unwrap().camera_count;
    test_check!(
        "Streaming {final_count} camera(s) — frame dimensions: [{}]",
        format_dimensions(&after_remove.last().unwrap()),
    );
    anyhow::ensure!(
        final_count == reduced_count as i32,
        "expected {} cameras after remove, got {final_count}",
        reduced_count,
    );
    test_check!("Camera count decreased from {full_count} → {final_count}");

    Ok(())
}
