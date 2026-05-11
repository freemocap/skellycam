//! Minimal wrapper around `nokhwa::Camera` for raw frame grab.
//! The camera is `!Send` and must stay on its creation thread.
//! This struct encapsulates all nokhwa access.

use anyhow::{Context, Result};
use nokhwa::pixel_format::RgbFormat;
use nokhwa::utils::{
    ApiBackend, CameraIndex, RequestedFormat, RequestedFormatType, Resolution,
};
use nokhwa::Camera;

/// Owns a nokhwa `Camera` and exposes raw grab operations.
/// Not `Send` — must stay on the thread where the camera was opened.
pub struct CameraManager {
    camera: Camera,
    pub camera_name: String,
    pub width: u32,
    pub height: u32,
}

impl CameraManager {
    /// Open the camera on the current thread.
    ///
    /// Uses `AbsoluteHighestFrameRate` with `RgbFormat` to let nokhwa
    /// negotiate the best available format.  The actual resolution may
    /// differ from the requested one — always read `width`/`height` after open.
    pub fn open(index: u32, requested_width: u32, requested_height: u32) -> Result<Self> {
        let cameras = nokhwa::query(ApiBackend::Auto)?;
        if index as usize >= cameras.len() {
            anyhow::bail!(
                "Camera index {index} is out of range (found {} camera(s)).",
                cameras.len()
            );
        }

        let camera_name = cameras[index as usize].human_name();

        let requested_format =
            RequestedFormat::new::<RgbFormat>(RequestedFormatType::AbsoluteHighestFrameRate);
        let mut camera = Camera::new(CameraIndex::Index(index), requested_format)
            .context("Failed to create camera handle — camera may be in use by another application.")?;

        if requested_width > 0 && requested_height > 0 {
            let resolution = Resolution::new(requested_width, requested_height);
            if camera.set_resolution(resolution).is_ok() {
                tracing::info!(
                    "Requested resolution {requested_width}x{requested_height}"
                );
            }
        }

        camera
            .open_stream()
            .context("Failed to start the camera stream.")?;

        let actual = camera.resolution();
        let width = actual.width();
        let height = actual.height();

        tracing::info!("Camera opened: {camera_name} at {width}x{height}");

        Ok(Self {
            camera,
            camera_name,
            width,
            height,
        })
    }

    /// Grab one raw frame from the camera.
    ///
    /// Returns the raw encoded bytes (typically MJPEG).  No decoding
    /// happens here — decoding is done on the decoder thread.
    /// This keeps the camera thread as thin and fast as possible.
    pub fn grab_raw(&mut self) -> Result<Vec<u8>> {
        let buffer = self
            .camera
            .frame()
            .context("Failed to grab frame — the camera may have been disconnected.")?;

        Ok(buffer.buffer().to_vec())
    }

    /// Stop the camera stream.
    pub fn close(&mut self) -> Result<()> {
        self.camera.stop_stream()?;
        tracing::info!("Camera stream stopped.");
        Ok(())
    }
}
