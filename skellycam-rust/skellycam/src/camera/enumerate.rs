//! Camera enumeration via openpnp-capture.
//!
//! Each camera gets a unique 6-character hex identifier derived from a hash of
//! all available identifying information (display name, device path, and index).

use std::hash::{Hash, Hasher};

use super::ffi::*;
use super::types::CameraIdentity;

/// Extract VID and PID from the USB device path.
/// Path format: `...\\?\usb#vid_0c45&pid_636b&mi_00#6&1f034fda...#...`
/// VID/PID appear in the same `#`-delimited segment: `vid_XXXX&pid_XXXX&mi_XX`.
fn parse_vid_pid(device_path: &str) -> (String, String) {
    let vid = device_path
        .split('#')
        .find(|s| s.starts_with("vid_"))
        .and_then(|segment| segment.split('&').find(|p| p.starts_with("vid_")))
        .unwrap_or("vid_????")
        .to_string();
    let pid = device_path
        .split('#')
        .find(|s| s.starts_with("vid_"))
        .and_then(|segment| segment.split('&').find(|p| p.starts_with("pid_")))
        .unwrap_or("pid_????")
        .to_string();
    (vid, pid)
}

/// Generate a 6-character hex ID from all available identifying information.
/// Hashes display name, device path, and camera index together.
fn make_unique_id(display_name: &str, device_path: &str, index: u32) -> String {
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    display_name.hash(&mut hasher);
    device_path.hash(&mut hasher);
    index.hash(&mut hasher);
    let hash = hasher.finish();
    format!("{:06x}", (hash >> 48) as u16)
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
            let short_id = make_unique_id(&display_name, &device_path, index);

            let has_mjpg = (0..num_formats).any(|f| {
                let mut info = CapFormatInfo::default();
                Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) == CAPRESULT_OK
                    && info.fourcc == FOURCC_MJPG
            });
            let mjpg_flag = if has_mjpg { " MJPG" } else { "" };

            eprintln!("    [{index}] \"{display_name}\"");
            eprintln!("           → id=[{short_id}]  {vid}  {pid}  formats={num_formats}{mjpg_flag}");

            cameras.push(CameraIdentity {
                display_name,
                camera_index: index as i32,
                unique_identifier: short_id,
                device_path,
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
