//! Camera detection via openpnp-capture.
//!
//! Each camera gets a unique 4-character hex identifier by SHA-256 hashing all
//! available identity fields (index, camera name, device path, VID/PID) and
//! taking the last 4 hex characters of the digest.

use sha2::{Digest, Sha256};

use super::ffi::*;
use super::types::{CameraDetection, CameraFormatInfo, CameraIdentity};

/// Convert a FOURCC u32 to its 4-character string representation.
/// FOURCC codes are stored little-endian in the u32: byte 0 = char 0, etc.
fn fourcc_to_str(fourcc: u32) -> String {
    let bytes = fourcc.to_le_bytes();
    bytes
        .iter()
        .map(|&b| {
            if b.is_ascii_graphic() || b == b' ' {
                b as char
            } else {
                '?'
            }
        })
        .collect()
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

/// Generate a 4-character hex camera ID from all available identity fields.
///
/// Concatenates index, camera name, device path, and VID/PID (when available)
/// into a single string, SHA-256 hashes it, and returns the last 4 hex
/// characters. Every field the OS reports contributes to the fingerprint —
/// maximally stable across Mac, Windows, and Linux.
fn make_unique_id(
    index: u32,
    camera_name: &str,
    device_path: &str,
    vendor_id: Option<u16>,
    product_id: Option<u16>,
) -> String {
    let mut raw = format!("index:{index}|name:{camera_name}|path:{device_path}|");
    if let (Some(vid), Some(pid)) = (vendor_id, product_id) {
        raw.push_str(&format!("vid:{vid:04x}|pid:{pid:04x}"));
    }

    let digest: [u8; 32] = Sha256::digest(raw.as_bytes()).into();
    let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();
    hex[hex.len() - 4..].to_string()
}

/// Detect all DirectShow cameras attached to the system.
///
/// Enumerates device names, paths, and formats. Filters out virtual cameras
/// and devices without MJPG formats. All cameras that pass filtering are
/// returned as available.
pub fn detect_cameras() -> anyhow::Result<Vec<CameraDetection>> {
    let detections = unsafe {
        let ctx = Cap_createContext();
        if ctx.is_null() {
            anyhow::bail!("Cap_createContext returned null during detection");
        }

        let device_count = Cap_getDeviceCount(ctx);
        tracing::info!(
            "  -- Camera Detection --\n  openpnp-capture reports {device_count} device(s)\n"
        );

        let mut detections: Vec<CameraDetection> = Vec::new();
        let mut filtered_no_formats: u32 = 0;
        let mut filtered_virtual: u32 = 0;
        let mut filtered_no_mjpg: u32 = 0;

        for index in 0..device_count {
            let display_name = cstr_to_string(Cap_getDeviceName(ctx, index))
                .unwrap_or_else(|| format!("Camera {index}"));
            let device_path = cstr_to_string(Cap_getDeviceUniqueID(ctx, index))
                .unwrap_or_default();
            let num_formats = Cap_getNumFormats(ctx, index);

            if display_name.to_lowercase().contains("virtual") {
                tracing::debug!(
                    "    [{index}] \"{display_name}\" — VIRTUAL CAMERA, skipping"
                );
                filtered_virtual += 1;
                continue;
            }

            if num_formats <= 0 {
                tracing::debug!(
                    "    [{index}] \"{display_name}\" — NO FORMATS, skipping"
                );
                filtered_no_formats += 1;
                continue;
            }

            let (vid, pid) = parse_vid_pid(&device_path);
            let short_id = make_unique_id(index, &display_name, &device_path, vid, pid);

            let mut formats: Vec<CameraFormatInfo> =
                Vec::with_capacity(num_formats as usize);
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

            if !has_mjpg {
                tracing::debug!(
                    "    [{index}] \"{display_name}\" — NO MJPG FORMAT, skipping (has {} formats: {:?})",
                    num_formats,
                    formats.iter().map(|f| f.fourcc_str.as_str()).collect::<Vec<_>>()
                );
                filtered_no_mjpg += 1;
                continue;
            }

            let vid_str = vid.map_or("????".to_string(), |v| format!("{v:04x}"));
            let pid_str = pid.map_or("????".to_string(), |p| format!("{p:04x}"));
            tracing::info!(
                "[{index}] {display_name} id:[{short_id}]  vid_{vid_str}  pid_{pid_str}  formats={num_formats} MJPG"
            );

            detections.push(CameraDetection {
                identity: CameraIdentity {
                    camera_name: display_name,
                    camera_index: index as i32,
                    camera_id: short_id,
                    device_path,
                    formats,
                },
                available: true,
            });
        }

        let total_filtered = filtered_virtual + filtered_no_formats + filtered_no_mjpg;
        let mut summary = String::new();
        if total_filtered > 0 {
            summary.push('\n');
            if filtered_virtual > 0 {
                summary.push_str(&format!(
                    "  -- {filtered_virtual} virtual camera(s) filtered --\n"
                ));
            }
            if filtered_no_formats > 0 {
                summary.push_str(&format!(
                    "  -- {filtered_no_formats} camera(s) filtered (no formats) --\n"
                ));
            }
            if filtered_no_mjpg > 0 {
                summary.push_str(&format!(
                    "  -- {filtered_no_mjpg} camera(s) filtered (no MJPG format) --\n"
                ));
            }
        }
        summary.push_str(&format!(
            "  = {} camera(s) detected =",
            detections.len()
        ));
        tracing::info!("\n{summary}\n");

        Cap_releaseContext(ctx);
        detections
    };

    Ok(detections)
}
