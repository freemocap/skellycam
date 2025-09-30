use tauri::{AppHandle, Manager};
use std::fs::File;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use std::path::PathBuf;
use serde::Serialize;
use memmap2::Mmap;

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
    frame_number: u32,
    timestamp: u64,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct PerformanceStats {
    rust_read_fps: f64,
    rust_decode_fps: f64,
    rust_frame_count: u64,
    latest_server_fps: f64,
    latest_frame_number: u32,
    server_latest_frame_number: u32,
}

struct FrameState {
    latest_bitmap: Option<FrameBitmap>,
    is_running: bool,
    frame_count: u64,
    read_times: Vec<f64>,
    decode_times: Vec<f64>,
    last_read_time: Option<Instant>,
    latest_server_fps: f64,
    last_requested_frame: u32,
}

struct AppState {
    frame_state: Arc<Mutex<FrameState>>,
    ring_buffer: Arc<Mutex<Option<RingBufferReader>>>,
}

const MAGIC_NUMBER: u32 = 0xDEADBEEF;
const HEADER_SIZE: usize = 64;
const SLOT_HEADER_SIZE: usize = 24;
const METADATA_SIZE: usize = 32;

#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct RingBufferHeader {
    magic: u32,
    version: u32,
    capacity: u32,
    max_frame_size: u32,
    write_index: u64,
    latest_frame_number: u64,
    total_writes: u64,
    metadata_table_offset: u64,
}

impl RingBufferHeader {
    fn from_bytes(bytes: &[u8]) -> Option<Self> {
        if bytes.len() < HEADER_SIZE {
            return None;
        }

        let magic = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
        let version = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        let capacity = u32::from_le_bytes([bytes[8], bytes[9], bytes[10], bytes[11]]);
        let max_frame_size = u32::from_le_bytes([bytes[12], bytes[13], bytes[14], bytes[15]]);

        let write_index = u64::from_le_bytes([
            bytes[16], bytes[17], bytes[18], bytes[19],
            bytes[20], bytes[21], bytes[22], bytes[23],
        ]);
        let latest_frame_number = u64::from_le_bytes([
            bytes[24], bytes[25], bytes[26], bytes[27],
            bytes[28], bytes[29], bytes[30], bytes[31],
        ]);
        let total_writes = u64::from_le_bytes([
            bytes[32], bytes[33], bytes[34], bytes[35],
            bytes[36], bytes[37], bytes[38], bytes[39],
        ]);
        let metadata_table_offset = u64::from_le_bytes([
            bytes[40], bytes[41], bytes[42], bytes[43],
            bytes[44], bytes[45], bytes[46], bytes[47],
        ]);

        Some(RingBufferHeader {
            magic,
            version,
            capacity,
            max_frame_size,
            write_index,
            latest_frame_number,
            total_writes,
            metadata_table_offset,
        })
    }
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct FrameMetadata {
    frame_number: u32,
    sequence: u32,
    slot_index: u32,
    _padding: u32,
    frame_size: u64,
    timestamp: u64,
    valid: u64,
}

impl FrameMetadata {
    fn from_bytes(bytes: &[u8]) -> Option<Self> {
        if bytes.len() < METADATA_SIZE {
            return None;
        }

        let frame_number = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
        let sequence = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        let slot_index = u32::from_le_bytes([bytes[8], bytes[9], bytes[10], bytes[11]]);

        let frame_size = u64::from_le_bytes([
            bytes[12], bytes[13], bytes[14], bytes[15],
            bytes[16], bytes[17], bytes[18], bytes[19],
        ]);
        let timestamp = u64::from_le_bytes([
            bytes[20], bytes[21], bytes[22], bytes[23],
            bytes[24], bytes[25], bytes[26], bytes[27],
        ]);
        let valid = u64::from_le_bytes([
            bytes[28], bytes[29], bytes[30], bytes[31],
            0, 0, 0, 0,
        ]);

        Some(FrameMetadata {
            frame_number,
            sequence,
            slot_index,
            _padding: 0,
            frame_size,
            timestamp,
            valid,
        })
    }
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct FrameSlotHeader {
    valid: u32,
    frame_number: u32,
    frame_size: u64,
    timestamp: u64,
}

impl FrameSlotHeader {
    fn from_bytes(bytes: &[u8]) -> Option<Self> {
        if bytes.len() < SLOT_HEADER_SIZE {
            return None;
        }

        let valid = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
        let frame_number = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        let frame_size = u64::from_le_bytes([
            bytes[8], bytes[9], bytes[10], bytes[11],
            bytes[12], bytes[13], bytes[14], bytes[15],
        ]);
        let timestamp = u64::from_le_bytes([
            bytes[16], bytes[17], bytes[18], bytes[19],
            bytes[20], bytes[21], bytes[22], bytes[23],
        ]);

        Some(FrameSlotHeader {
            valid,
            frame_number,
            frame_size,
            timestamp,
        })
    }
}

struct RingBufferReader {
    file: File,
    header: RingBufferHeader,
    capacity: u32,
    max_frame_size: u32,
    slot_size: usize,
    metadata_table_offset: usize,
    slots_offset: usize,
}

impl RingBufferReader {
    fn new(path: PathBuf) -> Result<Self, String> {
        let file = File::open(&path)
            .map_err(|e| format!("Failed to open ring buffer: {}", e))?;

        let mmap = unsafe { Mmap::map(&file) }
            .map_err(|e| format!("Failed to mmap file: {}", e))?;

        let header = RingBufferHeader::from_bytes(&mmap)
            .ok_or("Failed to parse ring buffer header")?;

        if header.magic != MAGIC_NUMBER {
            return Err(format!("Invalid magic: 0x{:X}", header.magic));
        }

        if header.version != 3 {
            return Err(format!("Unsupported version: {}", header.version));
        }

        let slot_size = SLOT_HEADER_SIZE + header.max_frame_size as usize;
        let metadata_table_offset = header.metadata_table_offset as usize;
        let metadata_table_size = METADATA_SIZE * header.capacity as usize;
        let slots_offset = metadata_table_offset + metadata_table_size;

        println!("Ring Buffer Reader Initialized:");
        println!("   Path: {:?}", path);
        println!("   Version: {}", header.version);
        println!("   Capacity: {} frames", header.capacity);
        println!("   Latest frame: {}", header.latest_frame_number);

        Ok(RingBufferReader {
            file,
            header,
            capacity: header.capacity,
            max_frame_size: header.max_frame_size,
            slot_size,
            metadata_table_offset,
            slots_offset,
        })
    }

    fn refresh_header(&mut self) -> Result<(), String> {
        let mmap = unsafe { Mmap::map(&self.file) }
            .map_err(|e| format!("Failed to mmap: {}", e))?;

        self.header = RingBufferHeader::from_bytes(&mmap)
            .ok_or("Failed to parse header")?;

        Ok(())
    }

    fn get_latest_frame_number(&mut self) -> Result<u32, String> {
        self.refresh_header()?;
        Ok(self.header.latest_frame_number as u32)
    }

    fn find_frame_metadata(&self, mmap: &Mmap, frame_number: u32) -> Result<Option<FrameMetadata>, String> {
        for i in 0..self.capacity {
            let metadata_offset = self.metadata_table_offset + (i as usize * METADATA_SIZE);

            if metadata_offset + METADATA_SIZE > mmap.len() {
                continue;
            }

            let metadata_bytes = &mmap[metadata_offset..metadata_offset + METADATA_SIZE];
            let metadata = FrameMetadata::from_bytes(metadata_bytes)
                .ok_or("Failed to parse metadata")?;

            if metadata.valid == 1 && metadata.frame_number == frame_number {
                return Ok(Some(metadata));
            }
        }

        Ok(None)
    }

    fn read_frame_by_number(&self, mmap: &Mmap, frame_number: u32) -> Result<Option<(FrameSlotHeader, Vec<u8>)>, String> {
        let metadata = match self.find_frame_metadata(mmap, frame_number)? {
            Some(m) => m,
            None => return Ok(None),
        };

        let slot_offset = self.slots_offset + (metadata.slot_index as usize * self.slot_size);

        if slot_offset + self.slot_size > mmap.len() {
            return Err("Slot offset out of bounds".to_string());
        }

        let slot_header_bytes = &mmap[slot_offset..slot_offset + SLOT_HEADER_SIZE];
        let slot_header = FrameSlotHeader::from_bytes(slot_header_bytes)
            .ok_or("Failed to parse slot header")?;

        if slot_header.valid != 1 || slot_header.frame_number != frame_number {
            return Ok(None);
        }

        if slot_header.frame_size as usize > self.max_frame_size as usize {
            return Err(format!("Frame size too large: {}", slot_header.frame_size));
        }

        let data_offset = slot_offset + SLOT_HEADER_SIZE;
        let data_end = data_offset + slot_header.frame_size as usize;

        if data_end > mmap.len() {
            return Err("Frame data out of bounds".to_string());
        }

        let frame_data = mmap[data_offset..data_end].to_vec();

        Ok(Some((slot_header, frame_data)))
    }
}

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
        frame_state.last_requested_frame = 0;
    }

    let reader = RingBufferReader::new(PathBuf::from(path.clone()))?;

    {
        let mut rb = state.ring_buffer.lock().unwrap();
        *rb = Some(reader);
    }

    let frame_state_clone = state.frame_state.clone();

    thread::spawn(move || {
        let poll_duration = Duration::from_millis(poll_rate_ms);

        loop {
            let should_continue = {
                let state = match frame_state_clone.lock() {
                    Ok(s) => s,
                    Err(e) => {
                        eprintln!("Mutex poisoned: {}", e);
                        break;
                    }
                };
                state.is_running
            };

            if !should_continue {
                break;
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
async fn get_latest_frame_number_from_buffer(app: AppHandle) -> Result<u32, String> {
    let state = app.state::<AppState>();
    let mut rb = state.ring_buffer.lock().map_err(|e| e.to_string())?;

    match rb.as_mut() {
        Some(reader) => reader.get_latest_frame_number(),
        None => Err("Ring buffer not initialized".to_string()),
    }
}

#[tauri::command]
async fn request_frame(app: AppHandle, frame_number: u32) -> Result<Option<FrameBitmap>, String> {
    let state = app.state::<AppState>();

    let read_start = Instant::now();

    let mut rb_lock = state.ring_buffer.lock().map_err(|e| e.to_string())?;
    let reader = match rb_lock.as_mut() {
        Some(r) => r,
        None => return Err("Ring buffer not initialized".to_string()),
    };

    let mmap = unsafe { Mmap::map(&reader.file) }
        .map_err(|e| format!("Failed to mmap: {}", e))?;

    let frame_result = match reader.read_frame_by_number(&mmap, frame_number) {
        Ok(Some((slot_header, frame_data))) => Some((slot_header, frame_data)),
        Ok(None) => return Ok(None),
        Err(e) => return Err(format!("Read error: {}", e)),
    };

    let (_slot_header, frame_data) = match frame_result {
        Some(data) => data,
        None => return Ok(None),
    };

    let decode_start = Instant::now();

    let message = match root_as_shared_message(&frame_data) {
        Ok(msg) => msg,
        Err(e) => return Err(format!("Failed to parse FlatBuffer: {:?}", e)),
    };

    if message.magic() != MAGIC_NUMBER {
        return Err(format!("Invalid magic: 0x{:X}", message.magic()));
    }

    let frame = match message.frame() {
        Some(f) => f,
        None => return Err("No frame in message".to_string()),
    };

    let width = frame.width();
    let height = frame.height();
    let channels = frame.channels();
    let timestamp = frame.timestamp();
    let frame_number = frame.frame_number();

    let pixels = match frame.pixels() {
        Some(p) => p,
        None => return Err("No pixel data".to_string()),
    };

    let expected_size = (width * height * channels) as usize;
    let actual_size = pixels.len();

    if actual_size != expected_size {
        return Err(format!("Size mismatch: {} != {}", actual_size, expected_size));
    }

    // Convert to RGBA
    let rgba_capacity = (width * height * 4) as usize;
    let mut rgba_data = Vec::with_capacity(rgba_capacity);

    let conversion_ok = if channels == 3 {
        let mut i = 0;
        while i + 2 < actual_size {
            rgba_data.push(pixels.get(i));
            rgba_data.push(pixels.get(i + 1));
            rgba_data.push(pixels.get(i + 2));
            rgba_data.push(255);
            i += 3;
        }
        i == actual_size && rgba_data.len() == rgba_capacity
    } else if channels == 4 {
        for i in 0..actual_size {
            rgba_data.push(pixels.get(i));
        }
        rgba_data.len() == rgba_capacity
    } else {
        false
    };

    if !conversion_ok {
        return Err("Conversion failed".to_string());
    }

    let decode_end = Instant::now();

    let bitmap = FrameBitmap {
        width,
        height,
        data: rgba_data,
        frame_number,
        timestamp,
    };

    let mut frame_state = state.frame_state.lock().map_err(|e| e.to_string())?;

    if let Some(last_time) = frame_state.last_read_time {
        let read_time = read_start.duration_since(last_time).as_secs_f64() * 1000.0;
        frame_state.read_times.push(read_time);
        if frame_state.read_times.len() > 100 {
            frame_state.read_times.remove(0);
        }
    }

    let decode_time = decode_end.duration_since(decode_start).as_secs_f64() * 1000.0;
    frame_state.decode_times.push(decode_time);
    if frame_state.decode_times.len() > 100 {
        frame_state.decode_times.remove(0);
    }

    frame_state.last_read_time = Some(read_start);
    frame_state.latest_bitmap = Some(bitmap.clone());
    frame_state.frame_count += 1;
    frame_state.last_requested_frame = frame_number;

    if let Some(s) = message.status() {
        frame_state.latest_server_fps = s.fps() as f64;
    }

    Ok(Some(bitmap))
}

#[tauri::command]
async fn get_latest_frame(app: AppHandle) -> Result<Option<FrameBitmap>, String> {
    let latest_frame_num = get_latest_frame_number_from_buffer(app.clone()).await?;
    request_frame(app, latest_frame_num).await
}

#[tauri::command]
async fn get_performance_stats(app: AppHandle) -> Result<PerformanceStats, String> {
    let state = app.state::<AppState>();

    let (read_times, decode_times, frame_count, latest_server_fps, last_requested_frame) = {
        let frame_state = state.frame_state.lock().map_err(|e| e.to_string())?;
        (
            frame_state.read_times.clone(),
            frame_state.decode_times.clone(),
            frame_state.frame_count,
            frame_state.latest_server_fps,
            frame_state.last_requested_frame,
        )
    };

    let server_latest = match get_latest_frame_number_from_buffer(app.clone()).await {
        Ok(n) => n,
        Err(_) => 0,
    };

    Ok(PerformanceStats {
        rust_read_fps: calculate_fps(&read_times),
        rust_decode_fps: calculate_fps(&decode_times),
        rust_frame_count: frame_count,
        latest_server_fps,
        latest_frame_number: last_requested_frame,
        server_latest_frame_number: server_latest,
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
                last_requested_frame: 0,
            })),
            ring_buffer: Arc::new(Mutex::new(None)),
        })
        .invoke_handler(tauri::generate_handler![
            start_frame_reader,
            stop_frame_reader,
            get_latest_frame,
            get_latest_frame_number_from_buffer,
            request_frame,
            get_performance_stats,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}