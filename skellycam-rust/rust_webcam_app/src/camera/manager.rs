//! Wrapper around `nokhwa::Camera` that owns the camera and exposes the
//! operations needed by the camera thread.
//!
//! ## Why a wrapper?
//!
//! `nokhwa::Camera` is **not** `Send` — it can't cross thread boundaries.
//! `CameraManager` encapsulates all camera operations so the camera thread
//! closure in `ops.rs` only needs to call methods on this struct.
//!
//! ## Python analogy
//!
//! This is like wrapping `cv2.VideoCapture` in a class that lives on a single
//! thread:
//! ```python
//! class CameraManager:
//!     def __init__(self, index):
//!         self.cap = cv2.VideoCapture(index)  # must stay on this thread
//!     def capture(self):
//!         ret, frame = self.cap.read()
//!         return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ret else None
//! ```

use anyhow::{Context, Result};
use image::RgbImage;
use nokhwa::pixel_format::RgbFormat;
use nokhwa::utils::{
    ApiBackend, CameraIndex, ControlValueDescription, ControlValueSetter,
    KnownCameraControl, RequestedFormat, RequestedFormatType, Resolution,
};
use nokhwa::Camera;

// ── CameraManager (crate-internal) ────────────────────────────────────
//
// Owns a nokhwa `Camera` and exposes the raw operations needed by the
// camera thread.  Not `Send` by design — the camera must stay on the
// thread where it was opened.

/// Owns a nokhwa `Camera` and exposes capture + control operations.
///
/// This type is deliberately **not** `Send` — it must stay on the thread
/// where the camera was opened (platform API requirements).
pub(crate) struct CameraManager {
    camera: Camera,
    pub(crate) camera_name: String,
    pub(crate) width: u32,
    pub(crate) height: u32,
}

impl CameraManager {
    /// Open the camera on the **current** thread.
    ///
    /// Called inside the camera thread's closure.  Does not query supported
    /// controls — that was already done by `query_camera()` on the main thread
    /// and passed in via `CameraMetadata`.
    ///
    /// ## Rust concept: `?` operator
    ///
    /// The `?` at the end of fallible calls is like Python's `try:` — if the
    /// result is `Err`, the function returns immediately with that error.
    /// `.context(...)` wraps the error with a human-readable message (like
    /// Python's `raise ... from ...` for chaining exceptions).
    pub fn open_inner(index: u32, width: u32, height: u32) -> Result<Self> {
        let cameras = nokhwa::query(ApiBackend::Auto)?;
        if index as usize >= cameras.len() {
            anyhow::bail!(
                "Camera index {index} is out of range (found {} camera(s)).",
                cameras.len()
            );
        }

        let camera_name = cameras[index as usize].human_name();

        let requested =
            RequestedFormat::new::<RgbFormat>(RequestedFormatType::AbsoluteHighestFrameRate);
        let mut camera = Camera::new(CameraIndex::Index(index), requested)
            .context("Failed to create camera handle — camera may be in use by another app.")?;

        if width > 0 && height > 0 {
            let resolution = Resolution::new(width, height);
            if camera.set_resolution(resolution).is_ok() {
                println!("Set resolution to {width}x{height}");
            }
        }

        camera
            .open_stream()
            .context("Failed to start the camera stream.")?;

        let actual = camera.resolution();
        Ok(Self {
            camera,
            camera_name,
            width: actual.width(),
            height: actual.height(),
        })
    }

    /// Capture one frame and return it as an `RgbImage`.
    ///
    /// `RgbImage` wraps a `Vec<u8>` of raw RGB pixels (row-major, 3 bytes
    /// per pixel, no padding).  This is like:
    /// ```python
    /// ret, bgr = cap.read()
    /// rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    /// ```
    /// except nokhwa gives us RGB directly (no BGR conversion needed).
    pub fn capture(&mut self) -> Result<RgbImage> {
        let buffer = self
            .camera
            .frame()
            .context("Failed to grab frame — the camera may have been disconnected.")?;
        let rgb = buffer
            .decode_image::<RgbFormat>()
            .context("Failed to decode frame to RGB format.")?;
        Ok(rgb)
    }

    /// Query the current value and description of a camera control.
    ///
    /// Returns `(current_value, description)` where the value is coerced to
    /// `i64` for uniform handling (booleans → 0/1, floats → truncated to int).
    ///
    /// ## Rust concept: `match` on enum variants
    ///
    /// `ControlValueSetter` is an enum that can be `Integer(i64)`,
    /// `Boolean(bool)`, or `Float(f64)`.  The `match` expression destructures
    /// each variant and extracts the inner value — the compiler checks that
    /// all variants are handled.
    pub fn get_control_info(
        &self,
        control: KnownCameraControl,
    ) -> Result<(i64, ControlValueDescription)> {
        let control_handle = self.camera.camera_control(control)?;
        let description = control_handle.description().clone();
        let current = match control_handle.value() {
            ControlValueSetter::Integer(value) => value,
            ControlValueSetter::Boolean(boolean) => i64::from(boolean),
            ControlValueSetter::Float(float) => float as i64,
            other => anyhow::bail!("Control value is of unsupported type ({other:?})."),
        };
        Ok((current, description))
    }

    /// Adjust a camera control by `delta` step-sized increments.
    ///
    /// The step size comes from the control's description — for integer
    /// controls with `step=0`, we default to step=1.  The new value is
    /// clamped to `[min, max]` for range-constrained controls.
    ///
    /// ## Python analogy (OpenCV):
    /// ```python
    /// value = cap.get(cv2.CAP_PROP_BRIGHTNESS)
    /// cap.set(cv2.CAP_PROP_BRIGHTNESS, value + delta * step)
    /// ```
    /// OpenCV uses floating-point for all controls; nokhwa preserves the
    /// native type (integer, float, boolean) which gives finer control.
    pub fn adjust_control(&mut self, control: KnownCameraControl, delta: i64) -> Result<i64> {
        let control_handle = self.camera.camera_control(control)?;
        let description = control_handle.description().clone();

        let new_value = match &description {
            ControlValueDescription::IntegerRange {
                value,
                min: minimum,
                max: maximum,
                step,
                ..
            } => {
                let step_size = if *step == 0 { 1 } else { *step };
                (value + delta * step_size).clamp(*minimum, *maximum)
            }
            ControlValueDescription::Integer { value, step, .. } => {
                let step_size = if *step == 0 { 1 } else { *step };
                value + delta * step_size
            }
            ControlValueDescription::FloatRange {
                value,
                min: minimum,
                max: maximum,
                step,
                ..
            } => {
                let step_size = if *step == 0.0 { 1.0 } else { *step };
                let candidate = (value + delta as f64 * step_size).clamp(*minimum, *maximum);
                candidate as i64
            }
            ControlValueDescription::Float { value, step, .. } => {
                let step_size = if *step == 0.0 { 1.0 } else { *step };
                (value + delta as f64 * step_size) as i64
            }
            _ => anyhow::bail!("This control type does not support numeric adjustment."),
        };

        self.camera
            .set_camera_control(control, ControlValueSetter::Integer(new_value))
            .context("Failed to set camera control value.")?;

        Ok(new_value)
    }

    /// Stop the camera stream.  Called during graceful shutdown.
    pub fn close(&mut self) -> Result<()> {
        self.camera.stop_stream()?;
        Ok(())
    }
}
