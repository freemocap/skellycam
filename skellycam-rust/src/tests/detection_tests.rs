//! Camera detection tests.

use skellycam::camera::detect_cameras;

pub fn run(_args: &[String]) -> anyhow::Result<()> {
    run_basic_detection()
}

fn run_basic_detection() -> anyhow::Result<()> {
    let cameras = detect_cameras()?;
    if cameras.is_empty() {
        tracing::warn!("No cameras found.");
    } else {
        tracing::info!(
            "Found {} camera{} total.",
            cameras.len(),
            if cameras.len() == 1 { "" } else { "s" }
        );
        for cam in &cameras {
            tracing::info!(
                "  [{}] {} — {} format(s)",
                cam.camera_index,
                cam.camera_name,
                cam.formats.len(),
            );
        }
    }
    Ok(())
}
