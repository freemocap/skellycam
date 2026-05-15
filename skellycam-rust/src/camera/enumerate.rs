//! Camera enumeration via openpnp-capture.
//!
//! Each camera gets a unique 4-character hex identifier that matches the Python
//! `CameraDeviceInfo.camera_id` algorithm: SHA-256 of the USB device path,
//! first 2 bytes of the digest formatted as 4-char lowercase hex.
//!
//! This MUST match the algorithm in:
//!   skellycam/core/device_detection/detect_cameras_devices.py:CameraDeviceInfo.camera_id

use sha2::{Digest, Sha256};

use super::ffi::*;
use super::types::{CameraFormatInfo, CameraIdentity};

/// Convert a FOURCC u32 to its 4-character string representation.
/// FOURCC codes are stored little-endian in the u32: byte 0 = char 0, etc.
fn fourcc_to_str(fourcc: u32) -> String {
    let bytes = fourcc.to_le_bytes();
    // Filter non-ASCII bytes, replace with '?'
    bytes.iter().map(|&b| if b.is_ascii_graphic() || b == b' ' { b as char } else { '?' }).collect()
}

/// Extract VID and PID as numeric values from the USB device path.
/// Path format: `...\\?\usb#vid_0c45&pid_636b&mi_00#6&1f034fda...#...`
fn parse_vid_pid(device_path: &str) -> (Option<u16>, Option<u16>) {
    let segment = device_path.split('#').find(|s| s.starts_with("vid_"));
    let vid = segment
        .and_then(|s| s.split('&').find(|p| p.starts_with("vid_")))
        .and_then(|v| v.strip_prefix("vid_"))
        .and_then(|v| u16::from_str_radix(v, 16).ok());
    let pid = segment
        .and_then(|s| s.split('&').find(|p| p.starts_with("pid_")))
        .and_then(|p| p.strip_prefix("pid_"))
        .and_then(|p| u16::from_str_radix(p, 16).ok());
    (vid, pid)
}

/// Generate a 4-character hex ID matching the Python `CameraDeviceInfo.camera_id` algorithm.
///
/// Algorithm (must match detect_cameras_devices.py exactly):
///   1. If device_path is non-empty → raw = device_path
///   2. Else if VID/PID available → raw = "vid_pid_index" (4-char hex each)
///   3. Else → return "{index:04x}"
///   4. SHA-256(raw) → take bytes [0:2] → format as 4-char lowercase hex
fn make_unique_id(device_path: &str, vendor_id: Option<u16>, product_id: Option<u16>, index: u32) -> String {
    let raw = if !device_path.is_empty() {
        device_path.to_string()
    } else if let (Some(vid), Some(pid)) = (vendor_id, product_id) {
        format!("{vid:04x}_{pid:04x}_{index}")
    } else {
        return format!("{index:04x}");
    };

    let digest: [u8; 32] = Sha256::digest(raw.as_bytes()).into();
    let short = u16::from_be_bytes([digest[0], digest[1]]);
    format!("{short:04x}")
}

pub fn enumerate_directshow_cameras() -> anyhow::Result<Vec<CameraIdentity>> {
    unsafe {
        let ctx = Cap_createContext();
        if ctx.is_null() {
            anyhow::bail!("Cap_createContext returned null during enumeration");
        }

        let device_count = Cap_getDeviceCount(ctx);
        eprintln!("  ── Camera Detection ──");
        eprintln!("  openpnp-capture reports {device_count} device(s)\n");

        let mut cameras: Vec<CameraIdentity> = Vec::new();
        let mut filtered_count: u32 = 0;

        for index in 0..device_count {
            let display_name = cstr_to_string(Cap_getDeviceName(ctx, index))
                .unwrap_or_else(|| format!("Camera {index}"));
            let device_path = cstr_to_string(Cap_getDeviceUniqueID(ctx, index))
                .unwrap_or_default();
            let num_formats = Cap_getNumFormats(ctx, index);

            if num_formats <= 0 {
                eprintln!("    [{index}] \"{display_name}\" — no formats, skipping");
                filtered_count += 1;
                continue;
            }

            let (vid, pid) = parse_vid_pid(&device_path);
            let short_id = make_unique_id(&device_path, vid, pid, index as u32);

            // Collect all format info for this camera
            let mut formats: Vec<CameraFormatInfo> = Vec::with_capacity(num_formats as usize);
            let mut has_mjpg = false;
            for f in 0..num_formats {
                let mut info = CapFormatInfo::default();
                if Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) == CAPRESULT_OK {
                    if info.fourcc == FOURCC_MJPG {
                        has_mjpg = true;
                    }
                    formats.push(CameraFormatInfo {
                        width: info.width,
                        height: info.height,
                        fps: info.fps,
                        fourcc: info.fourcc,
                        fourcc_str: fourcc_to_str(info.fourcc),
                    });
                }
            }

            let mjpg_flag = if has_mjpg { " MJPG" } else { "" };

            let vid_str = vid.map_or("????".to_string(), |v| format!("{v:04x}"));
            let pid_str = pid.map_or("????".to_string(), |p| format!("{p:04x}"));

            eprintln!("    [{index}] \"{display_name}\"");
            eprintln!("           → id=[{short_id}]  vid_{vid_str}  pid_{pid_str}  formats={num_formats}{mjpg_flag}");

            cameras.push(CameraIdentity {
                display_name,
                camera_index: index as i32,
                unique_identifier: short_id,
                device_path,
                formats,
            });
        }

        Cap_releaseContext(ctx);

        if filtered_count > 0 {
            eprintln!("\n  ── {filtered_count} virtual camera(s) filtered ──");
        }
        eprintln!(
            "\n  = {cameras_len} physical camera(s) ready =\n",
            cameras_len = cameras.len()
        );

        Ok(cameras)
    }
}
