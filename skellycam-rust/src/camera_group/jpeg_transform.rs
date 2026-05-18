//! Lossless JPEG rotation via libjpeg-turbo `tjTransform`.
//!
//! Operates entirely in the DCT (compressed) domain — no decode to pixels,
//! no quality loss, ~1-2ms per frame. Wraps the turbojpeg C API directly
//! since we already statically link `turbojpeg-static.lib`.

#![allow(non_camel_case_types)]

use std::ffi::c_void;

type tjhandle = *mut c_void;

const TJXOP_ROT90: i32 = 5;
const TJXOP_ROT180: i32 = 6;
const TJXOP_ROT270: i32 = 7;

#[repr(C)]
#[derive(Clone, Copy)]
struct tjtransform {
    op: i32,
    options: i32,
    x: i32,
    y: i32,
    w: i32,
    h: i32,
}

unsafe extern "C" {
    fn tjInitTransform() -> tjhandle;
    fn tjTransform(
        handle: tjhandle,
        jpeg_buf: *const u8,
        jpeg_size: libc::c_ulong,
        n: i32,
        dst_bufs: *mut *mut u8,
        dst_sizes: *mut libc::c_ulong,
        transforms: *mut tjtransform,
        flags: i32,
    ) -> i32;
    fn tjDestroy(handle: tjhandle) -> i32;
    fn tjFree(buffer: *mut u8);
}

// We don't use libc types; define c_ulong for Windows x86_64
#[allow(non_camel_case_types)]
mod libc {
    pub type c_ulong = u32;
}

/// Losslessly rotate a JPEG byte buffer in the DCT domain.
///
/// `rotation` follows the Python `RotationTypes` convention:
///   -1 or 0  → no rotation (returns `None`)
///    0 (CW 90) → TJXOP_ROT90
///    1 (180)   → TJXOP_ROT180
///    2 (CCW 90) → TJXOP_ROT270 (inverse of ROT90)
///
/// Returns `Some(rotated_jpeg_bytes)` or `None` if no rotation needed.
pub fn rotate_jpeg_lossless(jpeg_bytes: &[u8], rotation: i32) -> Option<Vec<u8>> {
    let op = match rotation {
        0 => TJXOP_ROT90,
        1 => TJXOP_ROT180,
        2 => TJXOP_ROT270,
        -1 => return None,
        _ => return None,
    };

    unsafe {
        let handle = tjInitTransform();
        if handle.is_null() {
            // Fallback: return original bytes (no rotation, but no panic)
            return None;
        }

        let mut xform = tjtransform {
            op,
            options: 0,
            x: 0,
            y: 0,
            w: 0,
            h: 0,
        };

        let mut dst_buf: *mut u8 = std::ptr::null_mut();
        let mut dst_size: libc::c_ulong = 0;

        let ret = tjTransform(
            handle,
            jpeg_bytes.as_ptr(),
            jpeg_bytes.len() as libc::c_ulong,
            1,
            &mut dst_buf,
            &mut dst_size,
            &mut xform,
            0,
        );

        let result = if ret == 0 && !dst_buf.is_null() {
            let rotated = std::slice::from_raw_parts(dst_buf, dst_size as usize).to_vec();
            Some(rotated)
        } else {
            None
        };

        if !dst_buf.is_null() {
            tjFree(dst_buf);
        }
        tjDestroy(handle);

        result
    }
}
