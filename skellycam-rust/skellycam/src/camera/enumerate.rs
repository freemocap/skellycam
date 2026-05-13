//! Camera enumeration via openpnp-capture.

use super::ffi::*;
use super::types::CameraIdentity;

pub fn enumerate_directshow_cameras() -> anyhow::Result<Vec<CameraIdentity>> {
    unsafe {
        let ctx = Cap_createContext();
        if ctx.is_null() {
            anyhow::bail!("Cap_createContext returned null during enumeration");
        }

        let device_count = Cap_getDeviceCount(ctx);
        eprintln!("  openpnp-capture: {device_count} device(s) detected\n");

        let mut cameras: Vec<CameraIdentity> = Vec::new();
        let mut filtered_count: u32 = 0;

        for index in 0..device_count {
            let name = cstr_to_string(Cap_getDeviceName(ctx, index))
                .unwrap_or_else(|| format!("Camera {index}"));
            let unique_id = cstr_to_string(Cap_getDeviceUniqueID(ctx, index))
                .unwrap_or_default();
            let num_formats = Cap_getNumFormats(ctx, index);

            if num_formats <= 0 {
                eprintln!("    [{index}] {name} — no formats, skipping (virtual camera)");
                filtered_count += 1;
                continue;
            }

            let has_mjpg = (0..num_formats).any(|f| {
                let mut info = CapFormatInfo::default();
                Cap_getFormatInfo(ctx, index, f as CapFormatID, &mut info) == CAPRESULT_OK
                    && info.fourcc == FOURCC_MJPG
            });

            let format_summary = if has_mjpg { "MJPG" } else { "no-MJPG" };
            eprintln!(
                "    [{index}] {name}  ({num_formats} formats, {format_summary})"
            );

            let short_id = if unique_id.len() >= 6 {
                unique_id.chars().rev().take(6).collect::<String>().chars().rev().collect()
            } else {
                format!("{:06x}", index)
            };

            cameras.push(CameraIdentity {
                display_name: name,
                camera_index: index as i32,
                unique_identifier: short_id,
                device_path: unique_id,
            });
        }

        Cap_releaseContext(ctx);

        if filtered_count > 0 {
            eprintln!(
                "\n  Filtered out {filtered_count} virtual camera(s) (no formats)."
            );
        }
        eprintln!(
            "  {} physical camera(s) available.\n",
            cameras.len()
        );

        Ok(cameras)
    }
}
