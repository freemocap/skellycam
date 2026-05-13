use std::ffi::CStr;
use std::time::Instant;

// ---------------------------------------------------------------------------
// FFI: openpnp-capture.h — exact C API via extern "C"
// ---------------------------------------------------------------------------

type CapContext = *mut std::ffi::c_void;
type CapStream = i32;
type CapResult = u32;
type CapDeviceID = u32;
type CapFormatID = u32;

#[repr(C)]
#[derive(Debug, Clone, Copy, Default)]
struct CapFormatInfo {
    width: u32,
    height: u32,
    fourcc: u32,
    fps: u32,
    bpp: u32,
}

const CAPRESULT_OK: u32 = 0;
const CAPRESULT_ERR: u32 = 1;
const CAPRESULT_DEVICENOTFOUND: u32 = 2;
const CAPRESULT_FORMATNOTSUPPORTED: u32 = 3;
const CAPRESULT_PROPERTYNOTSUPPORTED: u32 = 4;

#[allow(dead_code)]
extern "C" {
    fn Cap_createContext() -> CapContext;
    fn Cap_releaseContext(ctx: CapContext) -> CapResult;
    fn Cap_getDeviceCount(ctx: CapContext) -> u32;
    fn Cap_getDeviceName(ctx: CapContext, index: CapDeviceID) -> *const std::ffi::c_char;
    fn Cap_getDeviceUniqueID(ctx: CapContext, index: CapDeviceID) -> *const std::ffi::c_char;
    fn Cap_getNumFormats(ctx: CapContext, index: CapDeviceID) -> i32;
    fn Cap_getFormatInfo(
        ctx: CapContext,
        index: CapDeviceID,
        id: CapFormatID,
        info: *mut CapFormatInfo,
    ) -> CapResult;
    fn Cap_openStream(ctx: CapContext, index: CapDeviceID, formatID: CapFormatID) -> CapStream;
    fn Cap_closeStream(ctx: CapContext, stream: CapStream) -> CapResult;
    fn Cap_isOpenStream(ctx: CapContext, stream: CapStream) -> u32;
    fn Cap_captureFrame(
        ctx: CapContext,
        stream: CapStream,
        buffer: *mut u8,
        buffer_bytes: u32,
    ) -> CapResult;
    fn Cap_hasNewFrame(ctx: CapContext, stream: CapStream) -> u32;
    fn Cap_getStreamFrameCount(ctx: CapContext, stream: CapStream) -> u32;
    // Camera property controls
    fn Cap_getPropertyLimits(
        ctx: CapContext,
        stream: CapStream,
        propID: u32,
        min: *mut i32,
        max: *mut i32,
        dValue: *mut i32,
    ) -> CapResult;
    fn Cap_setProperty(ctx: CapContext, stream: CapStream, propID: u32, value: i32) -> CapResult;
    fn Cap_setAutoProperty(ctx: CapContext, stream: CapStream, propID: u32, bOnOff: u32) -> CapResult;
    fn Cap_getProperty(ctx: CapContext, stream: CapStream, propID: u32, outValue: *mut i32) -> CapResult;
    fn Cap_getAutoProperty(ctx: CapContext, stream: CapStream, propID: u32, outValue: *mut u32) -> CapResult;
}

// Property ID constants from openpnp-capture.h
const CAPPROPID_EXPOSURE: u32 = 1;
const CAPPROPID_FOCUS: u32 = 2;
const CAPPROPID_ZOOM: u32 = 3;
const CAPPROPID_WHITEBALANCE: u32 = 4;
const CAPPROPID_GAIN: u32 = 5;

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

fn decode_fourcc(code: u32) -> String {
    let bytes = code.to_le_bytes();
    String::from_utf8_lossy(&bytes).to_string()
}

fn cstr_to_string(ptr: *const std::ffi::c_char) -> Option<String> {
    if ptr.is_null() {
        return None;
    }
    unsafe { CStr::from_ptr(ptr) }
        .to_str()
        .ok()
        .map(|s| s.to_string())
}

fn result_str(r: CapResult) -> &'static str {
    match r {
        CAPRESULT_OK => "OK",
        CAPRESULT_ERR => "ERR",
        CAPRESULT_DEVICENOTFOUND => "DEVICE_NOT_FOUND",
        CAPRESULT_FORMATNOTSUPPORTED => "FORMAT_NOT_SUPPORTED",
        CAPRESULT_PROPERTYNOTSUPPORTED => "PROPERTY_NOT_SUPPORTED",
        _ => "UNKNOWN",
    }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

fn main() {
    let camera_index: CapDeviceID = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    eprintln!("Using camera index {camera_index}\n");

    unsafe {
        let ctx = Cap_createContext();
        if ctx.is_null() {
            eprintln!("Cap_createContext returned null — aborting");
            std::process::exit(1);
        }

        // ----- enumerate --------------------------------------------------
        let device_count = Cap_getDeviceCount(ctx);
        println!("Devices: {device_count}\n");

        for i in 0..device_count {
            let name = cstr_to_string(Cap_getDeviceName(ctx, i))
                .unwrap_or_else(|| "<null>".into());
            let unique = cstr_to_string(Cap_getDeviceUniqueID(ctx, i))
                .unwrap_or_else(|| "<null>".into());
            let num_formats = Cap_getNumFormats(ctx, i);

            println!("  [{i}] {name}");
            println!("      unique:  {unique}");
            println!("      formats: {num_formats}");

            // print first few MJPG formats
            for f in 0..num_formats.min(4) {
                let mut info = CapFormatInfo::default();
                if Cap_getFormatInfo(ctx, i, f as CapFormatID, &mut info) == CAPRESULT_OK {
                    println!(
                        "        format {f}: {}x{} @{}fps  {}bpp  {}",
                        info.width,
                        info.height,
                        info.fps,
                        info.bpp,
                        decode_fourcc(info.fourcc),
                    );
                }
            }
            println!();
        }

        if device_count == 0 {
            eprintln!("No cameras found — exiting");
            Cap_releaseContext(ctx);
            return;
        }

        // ----- find MJPG 1280x720 format on chosen camera -------------------
        if camera_index >= device_count {
            eprintln!("Camera {camera_index} not found (only {device_count} devices)");
            Cap_releaseContext(ctx);
            std::process::exit(1);
        }
        let num_formats = Cap_getNumFormats(ctx, camera_index);
        let mut chosen_format: Option<CapFormatID> = None;
        let mut chosen_info = CapFormatInfo::default();

        let target_fourcc = 0x47504A4Du32; // MJPG on Windows DirectShow

        for f in 0..num_formats {
            let mut info = CapFormatInfo::default();
            if Cap_getFormatInfo(ctx, camera_index, f as CapFormatID, &mut info) == CAPRESULT_OK {
                let is_mjpg = info.fourcc == target_fourcc;
                let is_720p = info.width == 1280 && info.height == 720;
                if is_mjpg && is_720p {
                    chosen_format = Some(f as CapFormatID);
                    chosen_info = info;
                    break;
                }
            }
        }

        let format_id = if let Some(f) = chosen_format {
            println!(
                "Using format {f}: {}x{} @{}fps {}",
                chosen_info.width,
                chosen_info.height,
                chosen_info.fps,
                decode_fourcc(chosen_info.fourcc),
            );
            f
        } else {
            // fallback: first MJPG format at any resolution
            let mut fallback: Option<CapFormatID> = None;
            for f in 0..num_formats {
                let mut info = CapFormatInfo::default();
                if Cap_getFormatInfo(ctx, camera_index, f as CapFormatID, &mut info) == CAPRESULT_OK
                    && info.fourcc == target_fourcc
                {
                    fallback = Some(f as CapFormatID);
                    chosen_info = info;
                    break;
                }
            }
            if let Some(f) = fallback {
                println!(
                    "1280x720 MJPG not found — using format {f}: {}x{} @{}fps {}",
                    chosen_info.width,
                    chosen_info.height,
                    chosen_info.fps,
                    decode_fourcc(chosen_info.fourcc),
                );
                f
            } else {
                eprintln!("No MJPG format found on camera {camera_index}");
                Cap_releaseContext(ctx);
                std::process::exit(1);
            }
        };

        // ----- open stream -------------------------------------------------
        let stream = Cap_openStream(ctx, camera_index, format_id);
        if stream < 0 {
            eprintln!("Cap_openStream returned {stream} — aborting");
            Cap_releaseContext(ctx);
            std::process::exit(1);
        }
        println!("Stream {stream} opened\n");

        let frame_bytes = chosen_info.width as usize * chosen_info.height as usize * 3;
        let mut buffer: Vec<u8> = vec![0u8; frame_bytes];

        // --- Prime camera hardware by toggling auto-exposure ---
        // The C++ PoC and C test program both set camera properties
        // (exposure, focus, white balance, etc.) before measuring FPS.
        // These property writes go through the UVC (USB Video Class)
        // driver to the camera's image signal processor (ISP). Toggling
        // auto-exposure forces the ISP to re-initialize its pipeline,
        // which includes properly configuring the MJPEG encoder at the
        // requested framerate.
        // Without this, the camera may deliver frames at a reduced rate
        // even though the DirectShow media type promises 30fps.
        // --- Prime camera hardware by replicating the C++ PoC's property sequence ---
        // The C++ PoC sets auto-exposure OFF and exposure to -7 (2^-7 = 1/128s ≈ 7.8ms).
        // This forces a short sensor exposure time, which allows the camera's
        // MJPEG encoder pipeline to run at full 30fps (or faster).
        // Auto-exposure may choose longer exposures in typical indoor lighting,
        // which directly caps the camera's framerate since each frame takes longer.
        // The key insight: framerate is exposure-gated at the sensor level.
        println!("  Configuring camera properties (matching C++ PoC sequence)...");

        // Step 1: Get exposure limits to see what the camera supports
        let mut exp_min: i32 = 0;
        let mut exp_max: i32 = 0;
        let mut exp_default: i32 = 0;
        unsafe {
            let r = Cap_getPropertyLimits(ctx, stream, CAPPROPID_EXPOSURE,
                &mut exp_min, &mut exp_max, &mut exp_default);
            println!("    exposure limits: min={exp_min} max={exp_max} default={exp_default} (result={})", result_str(r));
        }

        // Step 2: Set auto-exposure OFF (manual mode)
        unsafe { Cap_setAutoProperty(ctx, stream, CAPPROPID_EXPOSURE, 0); }
        println!("    auto-exposure → MANUAL");

        // Step 3: Set exposure to -7 (matches C++ PoC's k_target_exposure)
        // This is 2^(-7) = 1/128s ≈ 7.8ms — fast enough for 30fps+
        let target_exposure: i32 = -7;
        unsafe {
            let r = Cap_setProperty(ctx, stream, CAPPROPID_EXPOSURE, target_exposure);
            println!("    exposure → {target_exposure} (result={})", result_str(r));
        }

        // Step 4: Let the camera stabilize with the new exposure
        // The camera's AEC (auto-exposure control) algorithm takes a few
        // frames to settle. We drain 30 frames without measuring.
        for _ in 0..30 {
            loop {
                if unsafe { Cap_hasNewFrame(ctx, stream) } != 0 { break; }
                std::thread::yield_now();
            }
            unsafe { Cap_captureFrame(ctx, stream, buffer.as_mut_ptr(), frame_bytes as u32); }
        }
        println!("    camera stabilized with new settings\n");

        const TOTAL_FRAMES: u32 = 300;

        let start = Instant::now();
        let mut total_read_ns: f64 = 0.0;
        let mut previous_timestamp = Instant::now();
        let mut total_interval_ns: f64 = 0.0;

        // Warmup: drain any buffered frames before measuring
        let mut warmup_count = 0;
        while Cap_hasNewFrame(ctx, stream) != 0 {
            Cap_captureFrame(ctx, stream, buffer.as_mut_ptr(), frame_bytes as u32);
            warmup_count += 1;
            if warmup_count > 100 {
                break;
            }
        }
        if warmup_count > 0 {
            println!("  (drained {warmup_count} warmup frames)\n");
        }
        previous_timestamp = Instant::now();

        for frame_number in 0..TOTAL_FRAMES {
            // Wait for next hardware frame
            let wait_start = Instant::now();
            loop {
                if Cap_hasNewFrame(ctx, stream) != 0 {
                    break;
                }
                std::thread::yield_now();
                // Safety valve: don't spin forever
                if wait_start.elapsed().as_secs_f64() > 5.0 {
                    eprintln!("Timeout waiting for frame {frame_number}");
                    break;
                }
            }

            let pre_capture = Instant::now();
            let result = Cap_captureFrame(ctx, stream, buffer.as_mut_ptr(), frame_bytes as u32);
            let post_capture = Instant::now();

            if result != CAPRESULT_OK {
                eprintln!(
                    "Frame {frame_number}: Cap_captureFrame returned {} ({})",
                    result,
                    result_str(result),
                );
                break;
            }

            total_read_ns += (post_capture - pre_capture).as_nanos() as f64;

            if frame_number > 0 {
                total_interval_ns +=
                    (pre_capture - previous_timestamp).as_nanos() as f64;
            }
            previous_timestamp = pre_capture;

            if frame_number > 0 && frame_number % 60 == 0 {
                let elapsed = start.elapsed().as_secs_f64();
                let fps = frame_number as f64 / elapsed;
                let avg_interval_us =
                    total_interval_ns / (frame_number as f64) / 1_000.0;
                let avg_read_us =
                    total_read_ns / (frame_number as f64) / 1_000.0;
                println!(
                    "  frame {frame_number:>4} | {fps:>5.1} fps | interval {avg_interval_us:>7.0} µs | read {avg_read_us:>6.0} µs",
                );
            }
        }

        let elapsed = start.elapsed().as_secs_f64();
        let stream_frame_count = Cap_getStreamFrameCount(ctx, stream);
        println!();
        println!("──────────────────────────────────────────");
        println!("  Total elapsed:  {elapsed:.3} seconds");
        println!("  Stream frames:  {stream_frame_count}");
        if elapsed > 0.0 {
            println!(
                "  Average FPS:    {:.1}",
                stream_frame_count as f64 / elapsed
            );
        }
        if stream_frame_count > 0 {
            println!(
                "  Average read:   {:.0} µs",
                total_read_ns / stream_frame_count as f64 / 1_000.0
            );
        }

        // ----- shutdown ----------------------------------------------------
        Cap_closeStream(ctx, stream);
        Cap_releaseContext(ctx);
        println!("  Shutdown:       clean");
    }
}
