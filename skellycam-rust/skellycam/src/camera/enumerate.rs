//! DirectShow camera enumeration via OpenCV.

use opencv::prelude::*;
use opencv::videoio;

use super::types::CameraIdentity;

/// FOURCC code for YUY2 (uncompressed YUV 4:2:2 packed format).
/// Virtual/software cameras typically use different FOURCC codes (e.g., NV12),
/// so filtering to YUY2-only excludes them on most systems.
const FOURCC_YUY2: u32 = 0x32595559; // bytes: 'Y','U','Y','2'

/// Discover all DirectShow cameras by probing indices 0..15.
///
/// Each camera is opened briefly to query its properties, then released.
/// Only cameras reporting YUY2 FOURCC are included (filters out virtual cameras
/// that typically use NV12 or other formats).
pub fn enumerate_directshow_cameras() -> anyhow::Result<Vec<CameraIdentity>> {
    let mut all_infos: Vec<DetectedInfo> = Vec::new();
    let mut total_probed: u32 = 0;

    eprintln!("  Probing DirectShow camera indices 0..15...");

    for index in 0..16i32 {
        let info = match probe_index(index) {
            Some(info) => info,
            None => continue,
        };
        eprintln!(
            "    [{index}] found: {}  FOURCC={}  backend={}",
            info.resolution_label(),
            info.fourcc_str,
            info.backend,
        );
        total_probed += 1;
        all_infos.push(info);
    }

    eprintln!("  Probe complete: {total_probed} devices responded.\n");

    let (kept, filtered): (Vec<_>, Vec<_>) = all_infos
        .into_iter()
        .partition(|info| info.fourcc_val == FOURCC_YUY2);

    if !filtered.is_empty() {
        eprintln!(
            "  Filtered out {} non-YUY2 camera(s) (likely virtual):",
            filtered.len()
        );
        for info in &filtered {
            eprintln!(
                "    [{}] {}  FOURCC={}  ({})",
                info.index, info.resolution_label(), info.fourcc_str, info.backend,
            );
        }
        eprintln!();
    }

    if kept.is_empty() {
        eprintln!("\n  No YUY2 cameras detected.\n");
        return Ok(Vec::new());
    }

    print_detection_table(&kept);

    eprintln!(
        "  {}/{} cameras passed YUY2 filter.",
        kept.len(),
        total_probed as usize,
    );

    Ok(kept.into_iter().map(|info| info.into_identity()).collect())
}

struct DetectedInfo {
    index: i32,
    width: u32,
    height: u32,
    fps: f64,
    fourcc_val: u32,
    fourcc_str: String,
    backend: String,
}

impl DetectedInfo {
    fn resolution_label(&self) -> String {
        if self.width > 0 && self.height > 0 {
            format!("{}x{}", self.width, self.height)
        } else {
            "—".to_string()
        }
    }

    fn fps_label(&self) -> String {
        if self.fps > 0.0 {
            format!("{:.1}", self.fps)
        } else {
            "—".to_string()
        }
    }

    fn into_identity(self) -> CameraIdentity {
        let unique_identifier = format!("{:06x}", self.index);
        let device_path = format!("DirectShow://{}", self.index);
        let display_name = if self.width > 0 && self.height > 0 {
            format!("Camera {} ({}x{})", self.index, self.width, self.height)
        } else {
            format!("Camera {}", self.index)
        };

        CameraIdentity {
            display_name,
            camera_index: self.index,
            unique_identifier,
            device_path,
        }
    }
}

fn probe_index(index: i32) -> Option<DetectedInfo> {
    let mut capture = videoio::VideoCapture::new(index, videoio::CAP_DSHOW).ok()?;
    if !capture.is_opened().ok()? {
        return None;
    }

    let width = capture
        .get(videoio::CAP_PROP_FRAME_WIDTH)
        .unwrap_or(0.0) as u32;
    let height = capture
        .get(videoio::CAP_PROP_FRAME_HEIGHT)
        .unwrap_or(0.0) as u32;
    let fps = capture.get(videoio::CAP_PROP_FPS).unwrap_or(0.0);
    let fourcc_val = capture
        .get(videoio::CAP_PROP_FOURCC)
        .unwrap_or(-1.0) as u32;
    let fourcc_str = if fourcc_val > 0 && fourcc_val < 0xFFFFFFFF {
        super::decode_fourcc(fourcc_val)
    } else {
        "—".to_string()
    };
    let backend = capture
        .get_backend_name()
        .unwrap_or_else(|_| "unknown".to_string());

    let _ = capture.release();

    Some(DetectedInfo {
        index,
        width,
        height,
        fps,
        fourcc_val,
        fourcc_str,
        backend,
    })
}

fn print_detection_table(cameras: &[DetectedInfo]) {
    if cameras.is_empty() {
        eprintln!("\n  No DirectShow cameras detected.\n");
        return;
    }

    let count = cameras.len();

    // Column widths
    const IDX_W: usize = 5;
    const RES_W: usize = 13;
    const FPS_W: usize = 7;
    const FOURCC_W: usize = 7;
    const BACKEND_W: usize = 10;
    const ID_W: usize = 6;

    let total_w = IDX_W + RES_W + FPS_W + FOURCC_W + BACKEND_W + ID_W + 7; // 7 separators

    // Build header string
    let header = format!(
        "  DETECTED {count} DIRECTSHOW CAMERA{}",
        if count == 1 { "" } else { "S" }
    );
    eprintln!();
    eprintln!("┌{0:─<total_w$}┐", "");
    eprintln!("│  {header:<pad$} │", pad = total_w - 4);
    eprintln!("├{0:─<total_w$}┤", "");
    eprintln!(
        "│ {:^idx_w$} │ {:^res_w$} │ {:^fps_w$} │ {:^fourcc_w$} │ {:^backend_w$} │ {:^id_w$} │",
        "Index",
        "Resolution",
        "FPS",
        "FOURCC",
        "Backend",
        "ID",
        idx_w = IDX_W,
        res_w = RES_W,
        fps_w = FPS_W,
        fourcc_w = FOURCC_W,
        backend_w = BACKEND_W,
        id_w = ID_W,
    );
    eprintln!("├{0:─<total_w$}┤", "");

    for cam in cameras {
        let id_str = format!("{:06x}", cam.index);
        eprintln!(
            "│ {:>idx_w$} │ {:>res_w$} │ {:>fps_w$} │ {:>fourcc_w$} │ {:>backend_w$} │ {:>id_w$} │",
            cam.index,
            cam.resolution_label(),
            cam.fps_label(),
            cam.fourcc_str,
            cam.backend,
            id_str,
            idx_w = IDX_W,
            res_w = RES_W,
            fps_w = FPS_W,
            fourcc_w = FOURCC_W,
            backend_w = BACKEND_W,
            id_w = ID_W,
        );
    }

    eprintln!("└{0:─<total_w$}┘", "");
    eprintln!();
}
