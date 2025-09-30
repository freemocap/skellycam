use tauri::{AppHandle, Manager};
use std::fs::File;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use serde::Serialize;
use memmap2::Mmap;

// Import generated FlatBuffer code
#[allow(unused_imports)]
mod generated {
    include!("generated/message_generated.rs");
}

use generated::shared_data::root_as_shared_message;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct FrameBitmap {
    width: u32,
    height: u32,
    data: Vec<u8>,
    sequence: u64,
    timestamp: u64,
    frame_number: u32,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct PerformanceStats {
    rust_read_fps: f64,
    rust_decode_fps: f64,
    rust_frame_count: u64,
    latest_server_fps: f64,
    latest_frame_number: u32,
}

struct FrameState {
    latest_bitmap: Option<FrameBitmap>,
    is_running: bool,
    frame_count: u64,
    read_times: Vec<f64>,
    decode_times: Vec<f64>,
    last_read_time: Option<Instant>,
    latest_server_fps: f64,
    last_sequence: u64,  // Track last seen sequence to detect new frames
}

struct AppState {
    frame_state: Arc<Mutex<FrameState>>,
}

const MAX_REASONABLE_SIZE: usize = 100 * 1024 * 1024; // 100MB max frame size
const MAGIC_NUMBER: u32 = 0xDEADBEEF;

#[tauri::command]
async fn start_frame_reader(
    app: AppHandle,
    path: String,
    poll_rate_ms: u64,
) -> Result<(), String> {
    let state = app.state::<AppState>();

    {
        let mut frame_state = state.frame_state.lock().unwrap();
        frame_state.is_running = true;
        frame_state.frame_count = 0;
        frame_state.read_times.clear();
        frame_state.decode_times.clear();
        frame_state.last_read_time = None;
        frame_state.last_sequence = 0;
    }

    let frame_state_clone = state.frame_state.clone();

    thread::spawn(move || {
        let poll_duration = Duration::from_millis(poll_rate_ms);

        // Open memory-mapped file
        let file = match File::open(&path) {
            Ok(f) => f,
            Err(e) => {
                eprintln!("Failed to open mmap file: {}", e);
                return;
            }
        };

        let mut consecutive_errors = 0;
        const MAX_CONSECUTIVE_ERRORS: u32 = 10;

        loop {
            // Check if we should continue
            let (should_continue, last_sequence) = {
                let state = match frame_state_clone.lock() {
                    Ok(s) => s,
                    Err(e) => {
                        eprintln!("Mutex poisoned, stopping: {}", e);
                        break;
                    }
                };
                (state.is_running, state.last_sequence)
            };

            if !should_continue {
                break;
            }

            let read_start = Instant::now();

            // Memory-map the file
            let mmap = match unsafe { Mmap::map(&file) } {
                Ok(m) => m,
                Err(e) => {
                    eprintln!("Failed to mmap file: {}", e);
                    thread::sleep(poll_duration);
                    continue;
                }
            };

            // Validate minimum size
            if mmap.len() < 4 {
                thread::sleep(poll_duration);
                continue;
            }

            // Read size prefix with bounds checking
            let size = u32::from_le_bytes([mmap[0], mmap[1], mmap[2], mmap[3]]) as usize;

            // Validate size is reasonable
            if size == 0 {
                thread::sleep(poll_duration);
                continue;
            }

            if size > MAX_REASONABLE_SIZE {
                consecutive_errors += 1;
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS {
                    eprintln!("Too many consecutive errors, size too large: {} bytes", size);
                    break;
                }
                thread::sleep(poll_duration);
                continue;
            }

            // Verify we have enough data
            if size > mmap.len() - 4 {
                // Data not fully written yet, wait
                thread::sleep(poll_duration);
                continue;
            }

            // Get FlatBuffer data
            let fb_data = &mmap[4..4 + size];

            let decode_start = Instant::now();

            // Parse FlatBuffer with error handling
            let message = match root_as_shared_message(fb_data) {
                Ok(msg) => msg,
                Err(e) => {
                    consecutive_errors += 1;
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS {
                        eprintln!("Too many consecutive FlatBuffer parse errors: {:?}", e);
                        break;
                    }
                    // Likely partial write, wait and retry
                    thread::sleep(poll_duration);
                    continue;
                }
            };

            // Verify magic number
            if message.magic() != MAGIC_NUMBER {
                consecutive_errors += 1;
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS {
                    eprintln!("Invalid magic number: 0x{:X}", message.magic());
                    break;
                }
                thread::sleep(poll_duration);
                continue;
            }

            // Reset error counter on successful parse
            consecutive_errors = 0;

            // Check if this is a new frame (sequence changed)
            let sequence = message.sequence();
            if sequence <= last_sequence {
                // Same frame as before, no new data yet
                thread::sleep(poll_duration);
                continue;
            }

            // Extract frame
            let frame = match message.frame() {
                Some(f) => f,
                None => {
                    eprintln!("No frame in message");
                    thread::sleep(poll_duration);
                    continue;
                }
            };

            let width = frame.width();
            let height = frame.height();
            let channels = frame.channels();
            let timestamp = frame.timestamp();
            let frame_number = frame.frame_number();

            // Get pixel data
            let pixels = match frame.pixels() {
                Some(p) => p,
                None => {
                    eprintln!("No pixel data in frame");
                    thread::sleep(poll_duration);
                    continue;
                }
            };

            // Validate pixel data size
            let expected_size = (width * height * channels) as usize;
            if pixels.len() != expected_size {
                eprintln!(
                    "Invalid pixel data size: expected {}, got {}",
                    expected_size,
                    pixels.len()
                );
                thread::sleep(poll_duration);
                continue;
            }

            // Convert RGB to RGBA for Canvas ImageData
            let mut rgba_data = Vec::with_capacity((width * height * 4) as usize);

            if channels == 3 {
                // RGB -> RGBA
                for i in (0..pixels.len()).step_by(3) {
                    rgba_data.push(pixels.get(i));
                    rgba_data.push(pixels.get(i + 1));
                    rgba_data.push(pixels.get(i + 2));
                    rgba_data.push(255); // Alpha
                }
            } else if channels == 4 {
                // Already RGBA
                for i in 0..pixels.len() {
                    rgba_data.push(pixels.get(i));
                }
            } else {
                eprintln!("Unsupported channel count: {}", channels);
                thread::sleep(poll_duration);
                continue;
            }

            let decode_end = Instant::now();

            // Create bitmap
            let bitmap = FrameBitmap {
                width,
                height,
                data: rgba_data,
                sequence,
                timestamp,
                frame_number,
            };

            // Update state with timing
            let mut state = match frame_state_clone.lock() {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("Mutex poisoned during update: {}", e);
                    break;
                }
            };

            if let Some(last_time) = state.last_read_time {
                let read_time = read_start.duration_since(last_time).as_secs_f64() * 1000.0;
                state.read_times.push(read_time);
                if state.read_times.len() > 100 {
                    state.read_times.remove(0);
                }
            }

            let decode_time = decode_end.duration_since(decode_start).as_secs_f64() * 1000.0;
            state.decode_times.push(decode_time);
            if state.decode_times.len() > 100 {
                state.decode_times.remove(0);
            }

            state.last_read_time = Some(read_start);
            state.latest_bitmap = Some(bitmap);
            state.frame_count += 1;
            state.last_sequence = sequence;

            if let Some(s) = message.status() {
                state.latest_server_fps = s.fps() as f64;
            }

            // Log every 100 frames
            if state.frame_count % 100 == 0 {
                let read_fps = calculate_fps(&state.read_times);
                let decode_fps = calculate_fps(&state.decode_times);
                let avg_decode = get_avg_time(&state.decode_times);

                println!(
                    "📖 RUST | Frame {:6} | Read: {:6.1} FPS | Decode: {:6.1} FPS | Avg decode: {:.2}ms",
                    state.frame_count, read_fps, decode_fps, avg_decode
                );
            }

            thread::sleep(poll_duration);
        }

        println!("Frame reader thread stopped");
    });

    Ok(())
}

#[tauri::command]
async fn stop_frame_reader(app: AppHandle) -> Result<(), String> {
    let state = app.state::<AppState>();
    let mut frame_state = state.frame_state.lock().map_err(|e| e.to_string())?;
    frame_state.is_running = false;
    Ok(())
}

#[tauri::command]
async fn get_latest_frame(app: AppHandle) -> Result<Option<FrameBitmap>, String> {
    let state = app.state::<AppState>();
    let frame_state = state.frame_state.lock().map_err(|e| e.to_string())?;
    Ok(frame_state.latest_bitmap.clone())
}

#[tauri::command]
async fn get_performance_stats(app: AppHandle) -> Result<PerformanceStats, String> {
    let state = app.state::<AppState>();
    let frame_state = state.frame_state.lock().map_err(|e| e.to_string())?;

    Ok(PerformanceStats {
        rust_read_fps: calculate_fps(&frame_state.read_times),
        rust_decode_fps: calculate_fps(&frame_state.decode_times),
        rust_frame_count: frame_state.frame_count,
        latest_server_fps: frame_state.latest_server_fps,
        latest_frame_number: frame_state.latest_bitmap.as_ref()
            .map(|b| b.frame_number)
            .unwrap_or(0),
    })
}

fn calculate_fps(times: &[f64]) -> f64 {
    if times.len() < 2 {
        return 0.0;
    }

    let avg_time: f64 = times.iter().sum::<f64>() / times.len() as f64;
    if avg_time > 0.0 {
        1000.0 / avg_time
    } else {
        0.0
    }
}

fn get_avg_time(times: &[f64]) -> f64 {
    if times.is_empty() {
        return 0.0;
    }
    times.iter().sum::<f64>() / times.len() as f64
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .manage(AppState {
            frame_state: Arc::new(Mutex::new(FrameState {
                latest_bitmap: None,
                is_running: false,
                frame_count: 0,
                read_times: Vec::new(),
                decode_times: Vec::new(),
                last_read_time: None,
                latest_server_fps: 0.0,
                last_sequence: 0,
            })),
        })
        .invoke_handler(tauri::generate_handler![
            start_frame_reader,
            stop_frame_reader,
            get_latest_frame,
            get_performance_stats,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}