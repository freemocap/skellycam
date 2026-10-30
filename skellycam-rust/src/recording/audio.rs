//! Native microphone capture. The Python adapter supplies the same PortAudio
//! library used for device enumeration, preserving the UI's device indices.
//! ABI/lifecycle and callback restrictions: [@portaudioV19Api].
//! WAV errors are checked on explicit finalization: [@hound351WavWriter].

use std::ffi::{c_char, c_int, c_ulong, c_void, CStr};
use std::path::PathBuf;
use std::sync::{Arc, atomic::{AtomicBool, AtomicUsize, Ordering}, mpsc};
use std::thread::JoinHandle;
use anyhow::{Context, Result, bail};
use libloading::Library;
use rtrb::{Producer, RingBuffer};
use serde_json::{Value, json};
use crate::timestamps::performance::performance_counter_nanoseconds;

const FRAMES: usize = 1024;
const RATE: u32 = 44_100;

#[repr(C)]
struct DeviceInfo {
    version: c_int, name: *const c_char, host_api: c_int,
    max_input_channels: c_int, max_output_channels: c_int,
    default_low_input_latency: f64, default_low_output_latency: f64,
    default_high_input_latency: f64, default_high_output_latency: f64,
    default_sample_rate: f64,
}
#[repr(C)]
struct Parameters {
    device: c_int, channel_count: c_int, sample_format: c_ulong,
    suggested_latency: f64, host_specific: *mut c_void,
}
#[repr(C)]
struct CallbackTime { input_adc: f64, current: f64, output_dac: f64 }
type Callback = unsafe extern "C" fn(*const c_void, *mut c_void, c_ulong,
    *const CallbackTime, c_ulong, *mut c_void) -> c_int;

struct Api {
    _library: Library,
    terminate: unsafe extern "C" fn() -> c_int,
    device: unsafe extern "C" fn(c_int) -> *const DeviceInfo,
    open: unsafe extern "C" fn(*mut *mut c_void, *const Parameters, *const Parameters,
        f64, c_ulong, c_ulong, Option<Callback>, *mut c_void) -> c_int,
    start: unsafe extern "C" fn(*mut c_void) -> c_int,
    stop: unsafe extern "C" fn(*mut c_void) -> c_int,
    close: unsafe extern "C" fn(*mut c_void) -> c_int,
    active: unsafe extern "C" fn(*mut c_void) -> c_int,
    error_text: unsafe extern "C" fn(c_int) -> *const c_char,
}
impl Api {
    unsafe fn load(path: &str) -> Result<Self> { unsafe {
        let lib = Library::new(path).context("loading application's PortAudio library")?;
        // Resolve all symbols before initialization so failures cannot leak a reference.
        let initialize = *lib.get::<unsafe extern "C" fn() -> c_int>(b"Pa_Initialize\0")?;
        let api = Self {
            terminate: *lib.get(b"Pa_Terminate\0")?, device: *lib.get(b"Pa_GetDeviceInfo\0")?,
            open: *lib.get(b"Pa_OpenStream\0")?, start: *lib.get(b"Pa_StartStream\0")?,
            stop: *lib.get(b"Pa_StopStream\0")?, close: *lib.get(b"Pa_CloseStream\0")?,
            active: *lib.get(b"Pa_IsStreamActive\0")?, error_text: *lib.get(b"Pa_GetErrorText\0")?,
            _library: lib,
        };
        api.check(initialize())?;
        Ok(api)
    }}
    fn check(&self, code: c_int) -> Result<()> {
        if code < 0 {
            let text = unsafe { CStr::from_ptr((self.error_text)(code)) }.to_string_lossy();
            bail!("PortAudio {code}: {text}");
        }
        Ok(())
    }
}

struct Chunk {
    data: [i16; FRAMES * 2], samples: usize,
    timestamp: i64, adc_timestamp: i64, status: c_ulong,
}
struct CallbackState {
    producer: Producer<Chunk>, channels: usize, dropped: Arc<AtomicUsize>,
}

unsafe extern "C" fn callback(input: *const c_void, _output: *mut c_void,
    frames: c_ulong, time: *const CallbackTime, status: c_ulong, user: *mut c_void,
) -> c_int { unsafe {
    let state = &mut *user.cast::<CallbackState>();
    if input.is_null() || frames as usize > FRAMES {
        state.dropped.fetch_add(1, Ordering::Relaxed);
        return 0;
    }
    let timestamp = performance_counter_nanoseconds();
    let samples = frames as usize * state.channels;
    let mut chunk = Chunk { data: [0; FRAMES * 2], samples, timestamp,
        adc_timestamp: timestamp + (((*time).input_adc - (*time).current) * 1e9) as i64, status };
    chunk.data[..samples].copy_from_slice(std::slice::from_raw_parts(input.cast::<i16>(), samples));
    if state.producer.push(chunk).is_err() {
        state.dropped.fetch_add(1, Ordering::Relaxed);
    }
    0 // paContinue; shutdown happens on the owning worker thread.
}}

// All native handles and callback storage stay on one worker. Close the stream
// before dropping its callback state or unloading its library on every exit path.
struct Stream {
    handle: *mut c_void, api: Api, _callback: Box<CallbackState>,
}
impl Drop for Stream {
    fn drop(&mut self) { unsafe {
        if !self.handle.is_null() {
            (self.api.stop)(self.handle);
            (self.api.close)(self.handle);
        }
        (self.api.terminate)();
    }}
}

pub struct AudioRecorder {
    stop: Arc<AtomicBool>, worker: Option<JoinHandle<Result<Value>>>,
}
impl AudioRecorder {
    pub fn start(library: String, path: PathBuf, device: i32, mapping: Value) -> Result<Self> {
        let stop = Arc::new(AtomicBool::new(false));
        let worker_stop = stop.clone();
        let (ready_tx, ready_rx) = mpsc::sync_channel(1);
        let worker = std::thread::Builder::new().name("microphone-writer".into()).spawn(move || {
            capture(library, path, device, mapping, worker_stop, ready_tx)
        })?;
        let mut recorder = Self { stop, worker: Some(worker) };
        if ready_rx.recv().is_err() {
            return match recorder.stop() {
                Err(error) => Err(error),
                Ok(_) => Err(anyhow::anyhow!("audio worker ended before startup")),
            };
        }
        Ok(recorder)
    }
    pub fn stop(&mut self) -> Result<Value> {
        self.stop.store(true, Ordering::Release);
        self.worker.take().context("audio recording already stopped")?
            .join().map_err(|_| anyhow::anyhow!("audio worker panicked"))?
    }
}
impl Drop for AudioRecorder {
    fn drop(&mut self) {
        if self.worker.is_some() {
            if let Err(error) = self.stop() { tracing::error!("Audio shutdown: {error:#}"); }
        }
    }
}

fn capture(library: String, path: PathBuf, device: i32, mapping: Value,
    stop: Arc<AtomicBool>, ready: mpsc::SyncSender<()>,
) -> Result<Value> {
    let (producer, mut consumer) = RingBuffer::new(256);
    let dropped = Arc::new(AtomicUsize::new(0));
    let api = unsafe { Api::load(&library)? };
    let mut stream = Stream { handle: std::ptr::null_mut(), api,
        _callback: Box::new(CallbackState { producer, channels: 0, dropped: dropped.clone() }) };
    let info = unsafe { (stream.api.device)(device).as_ref() }.context("invalid microphone device index")?;
    if info.max_input_channels < 1 { bail!("selected device has no input channels"); }
    let channels = info.max_input_channels.min(2) as usize;
    stream._callback.channels = channels;
    let params = Parameters { device, channel_count: channels as i32, sample_format: 0x8,
        suggested_latency: info.default_low_input_latency, host_specific: std::ptr::null_mut() };
    if let Some(parent) = path.parent() { std::fs::create_dir_all(parent)?; }
    // Refuse an existing recording instead of overwriting it.
    let file = std::fs::OpenOptions::new().write(true).create_new(true).open(&path)?;
    let mut wav = hound::WavWriter::new(std::io::BufWriter::new(file), hound::WavSpec {
        channels: channels as u16, sample_rate: RATE, bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    })?;
    stream.api.check(unsafe { (stream.api.open)(&mut stream.handle, &params, std::ptr::null(),
        RATE as f64, FRAMES as c_ulong, 0, Some(callback),
        (&mut *stream._callback as *mut CallbackState).cast()) })?;
    let start = performance_counter_nanoseconds();
    stream.api.check(unsafe { (stream.api.start)(stream.handle) })?;
    ready.send(()).context("audio startup caller disconnected")?;
    let mut timestamps = Vec::new();
    let mut adc_timestamps = Vec::new();
    let mut sample_counts = Vec::new();
    let mut flags = Vec::new();
    let mut total_frames = 0usize;
    let mut stopping = false;
    let mut stream_error = None;
    loop {
        if !stopping && stop.load(Ordering::Acquire) {
            if let Err(error) = stream.api.check(unsafe { (stream.api.stop)(stream.handle) }) {
                stream_error = Some(error.to_string());
            }
            stopping = true;
        }
        while let Ok(chunk) = consumer.pop() {
            for sample in &chunk.data[..chunk.samples] { wav.write_sample(*sample)?; }
            let frames = chunk.samples / channels;
            total_frames += frames;
            timestamps.push(chunk.timestamp);
            adc_timestamps.push(chunk.adc_timestamp);
            sample_counts.push(frames);
            flags.push(chunk.status);
        }
        if stopping { break; }
        let active = unsafe { (stream.api.active)(stream.handle) };
        if active != 1 {
            stream_error = Some(format!("microphone stream stopped unexpectedly ({active})"));
            stop.store(true, Ordering::Release);
        }
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
    wav.finalize()?;
    let lost = dropped.load(Ordering::Acquire);
    let status_errors = flags.iter().filter(|&&flag| flag != 0).count();
    let metadata = json!({
        "audio_file": path.file_name().and_then(|p| p.to_str()), "mic_device_index": device,
        "sample_rate": RATE, "channels": channels, "chunk_size": FRAMES,
        "total_chunks": timestamps.len(), "total_samples": total_frames,
        "start_perf_counter_ns": start, "end_perf_counter_ns": timestamps.last().copied().unwrap_or(start),
        "duration_seconds": total_frames as f64 / RATE as f64,
        "timebase_mapping": mapping, "chunk_timestamps_perf_ns": timestamps,
        "chunk_adc_timestamps_perf_ns": adc_timestamps, "chunk_sample_counts": sample_counts,
        "portaudio_status_flags": flags, "dropped_chunks": lost, "stream_error": stream_error,
    });
    let sidecar = path.with_file_name(format!("{}_timestamps.json", path.file_stem().unwrap().to_string_lossy()));
    let file = std::fs::OpenOptions::new().write(true).create_new(true).open(sidecar)?;
    serde_json::to_writer_pretty(file, &metadata)?;
    if lost != 0 || status_errors != 0 || stream_error.is_some() || total_frames == 0 {
        bail!("microphone recording incomplete: {lost} dropped chunks, {status_errors} status errors, stream={stream_error:?}, frames={total_frames}");
    }
    Ok(metadata)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn callback_preserves_stereo_samples_and_reports_queue_overflow() {
        crate::timestamps::performance::anchor_performance_clock();
        let (producer, mut consumer) = RingBuffer::new(1);
        let dropped = Arc::new(AtomicUsize::new(0));
        let mut state = CallbackState { producer, channels: 2, dropped: dropped.clone() };
        let input = [1i16, -2, 3, -4];
        let time = CallbackTime { input_adc: 1.0, current: 1.01, output_dac: 0.0 };
        for _ in 0..2 { unsafe {
            callback(input.as_ptr().cast(), std::ptr::null_mut(), 2, &time, 0,
                (&mut state as *mut CallbackState).cast());
        }}
        let chunk = consumer.pop().unwrap();
        assert_eq!(&chunk.data[..chunk.samples], &input);
        assert_eq!(chunk.timestamp - chunk.adc_timestamp, 10_000_000);
        assert_eq!(dropped.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn null_input_is_reported_without_dereferencing_it() {
        let (producer, mut consumer) = RingBuffer::new(1);
        let dropped = Arc::new(AtomicUsize::new(0));
        let mut state = CallbackState { producer, channels: 2, dropped: dropped.clone() };
        unsafe { callback(std::ptr::null(), std::ptr::null_mut(), 1024, std::ptr::null(), 0,
            (&mut state as *mut CallbackState).cast()); }
        assert!(consumer.pop().is_err());
        assert_eq!(dropped.load(Ordering::Relaxed), 1);
    }
}
