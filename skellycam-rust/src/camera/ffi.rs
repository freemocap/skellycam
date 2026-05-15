//! Raw FFI bindings for the openpnp-capture C library.
//!
//! Safety contract: CapContext and CapStream wrap DirectShow COM objects.
//! They must be created, used, and destroyed on the same OS thread.

use std::ffi::{c_char, c_void, CStr};

pub type CapContext = *mut c_void;
pub type CapStream = i32;
pub type CapResult = u32;
pub type CapDeviceID = u32;
pub type CapFormatID = u32;

#[repr(C)]
#[derive(Debug, Clone, Copy, Default)]
pub struct CapFormatInfo {
    pub width: u32,
    pub height: u32,
    pub fourcc: u32,
    pub fps: u32,
    pub bpp: u32,
}

pub const CAPRESULT_OK: u32 = 0;
pub const CAPRESULT_ERR: u32 = 1;
pub const CAPRESULT_DEVICENOTFOUND: u32 = 2;
pub const CAPRESULT_FORMATNOTSUPPORTED: u32 = 3;
pub const CAPRESULT_PROPERTYNOTSUPPORTED: u32 = 4;

pub const CAPPROPID_EXPOSURE: u32 = 1;
pub const CAPPROPID_FOCUS: u32 = 2;
pub const CAPPROPID_ZOOM: u32 = 3;
pub const CAPPROPID_WHITEBALANCE: u32 = 4;
pub const CAPPROPID_GAIN: u32 = 5;

pub const FOURCC_MJPG: u32 = 0x47504A4D;

unsafe extern "C" {
    pub fn Cap_createContext() -> CapContext;
    pub fn Cap_releaseContext(ctx: CapContext) -> CapResult;
    pub fn Cap_getDeviceCount(ctx: CapContext) -> u32;
    pub fn Cap_getDeviceName(ctx: CapContext, index: CapDeviceID) -> *const c_char;
    pub fn Cap_getDeviceUniqueID(ctx: CapContext, index: CapDeviceID) -> *const c_char;
    pub fn Cap_getNumFormats(ctx: CapContext, index: CapDeviceID) -> i32;
    pub fn Cap_getFormatInfo(
        ctx: CapContext,
        index: CapDeviceID,
        id: CapFormatID,
        info: *mut CapFormatInfo,
    ) -> CapResult;
    pub fn Cap_openStream(ctx: CapContext, index: CapDeviceID, format_id: CapFormatID) -> CapStream;
    pub fn Cap_closeStream(ctx: CapContext, stream: CapStream) -> CapResult;
    pub fn Cap_isOpenStream(ctx: CapContext, stream: CapStream) -> u32;
    pub fn Cap_captureFrame(
        ctx: CapContext,
        stream: CapStream,
        buffer: *mut u8,
        buffer_bytes: u32,
    ) -> CapResult;
    pub fn Cap_hasNewFrame(ctx: CapContext, stream: CapStream) -> u32;
    pub fn Cap_getStreamFrameCount(ctx: CapContext, stream: CapStream) -> u32;
    pub fn Cap_getPropertyLimits(
        ctx: CapContext,
        stream: CapStream,
        property_id: u32,
        min: *mut i32,
        max: *mut i32,
        default_value: *mut i32,
    ) -> CapResult;
    pub fn Cap_setProperty(
        ctx: CapContext,
        stream: CapStream,
        property_id: u32,
        value: i32,
    ) -> CapResult;
    pub fn Cap_setAutoProperty(
        ctx: CapContext,
        stream: CapStream,
        property_id: u32,
        on_off: u32,
    ) -> CapResult;
    pub fn Cap_getProperty(
        ctx: CapContext,
        stream: CapStream,
        property_id: u32,
        out_value: *mut i32,
    ) -> CapResult;
    pub fn Cap_getAutoProperty(
        ctx: CapContext,
        stream: CapStream,
        property_id: u32,
        out_value: *mut u32,
    ) -> CapResult;

    // ── Raw MJPEG API (no RGB decode in capture loop) ──────────────

    /// Open a stream in raw MJPEG mode. Takes a format_id (same as Cap_openStream)
    /// so the caller can select the exact resolution/framerate/MJPG format.
    /// Returns -1 if the format isn't MJPEG.
    pub fn Cap_openStreamRaw(
        ctx: CapContext,
        index: CapDeviceID,
        format_id: CapFormatID,
    ) -> CapStream;

    /// Copy the latest raw JPEG frame into `buf`. `buf_size` is the capacity;
    /// the actual byte count is written to `*out_bytes`. Returns CAPRESULT_ERR
    /// if the caller's buffer is too small (and sets `*out_bytes` to the
    /// required size).
    pub fn Cap_captureFrameRaw(
        ctx: CapContext,
        stream: CapStream,
        buf: *mut u8,
        buf_size: u32,
        out_bytes: *mut u32,
    ) -> CapResult;

    /// Get the byte size of the current raw frame without copying.
    /// Writes the size to `*out_bytes`. Returns CAPRESULT_OK on success.
    pub fn Cap_getFrameSize(
        ctx: CapContext,
        stream: CapStream,
        out_bytes: *mut u32,
    ) -> CapResult;

    /// Decode the current raw JPEG frame into 24-bit RGB on demand.
    /// `RGBbufferBytes` must be at least `width * height * 3` bytes.
    /// Only valid on streams opened with `Cap_openStreamRaw`.
    pub fn Cap_decodeFrame(
        ctx: CapContext,
        stream: CapStream,
        RGBbufferPtr: *mut u8,
        RGBbufferBytes: u32,
    ) -> CapResult;
}

pub unsafe fn cstr_to_string(ptr: *const c_char) -> Option<String> {
    if ptr.is_null() {
        return None;
    }
    unsafe { CStr::from_ptr(ptr) }.to_str().ok().map(|s| s.to_string())
}

pub fn result_name(result: CapResult) -> &'static str {
    match result {
        CAPRESULT_OK => "OK",
        CAPRESULT_ERR => "ERR",
        CAPRESULT_DEVICENOTFOUND => "DEVICE_NOT_FOUND",
        CAPRESULT_FORMATNOTSUPPORTED => "FORMAT_NOT_SUPPORTED",
        CAPRESULT_PROPERTYNOTSUPPORTED => "PROPERTY_NOT_SUPPORTED",
        _ => "UNKNOWN",
    }
}
