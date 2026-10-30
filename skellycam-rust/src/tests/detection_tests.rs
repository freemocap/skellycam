//! Camera detection tests.

use skellycam::camera::detect_cameras;

pub fn run() -> anyhow::Result<()> {
    run_basic_detection()
}

fn run_basic_detection() -> anyhow::Result<()> {
    let detections = detect_cameras()?;
    if detections.is_empty() {
        tracing::warn!("No cameras found.");
    } else {
        tracing::info!(
            "Found {} camera{} total.",
            detections.len(),
            if detections.len() == 1 { "" } else { "s" }
        );
        for det in &detections {
            let cam = &det.identity;
            let avail = if det.available { "available" } else { "UNAVAILABLE" };
            tracing::info!(
                "  [{}] {} — {} format(s) — {}",
                cam.camera_index,
                cam.camera_name,
                cam.formats.len(),
                avail,
            );
            if !det.available {
                tracing::warn!(
                    "    ^ camera [{}] is unavailable (cannot connect)",
                    cam.camera_index,
                );
            }
        }
    }
    Ok(())
}
