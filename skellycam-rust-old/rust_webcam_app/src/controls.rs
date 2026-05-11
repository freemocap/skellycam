//! Camera control selection and keyboard-help display.
//!
//! Maps the number keys 1–9 to specific camera controls (brightness, contrast,
//! etc.) and provides helpers for printing control information.
//!
//! ## Python analogy
//!
//! `KnownCameraControl` is an **enum** — think of it as a fixed set of named
//! constants, but with compile-time exhaustiveness checking.  If you've used
//! Python's `Enum`, it's similar, except Rust enums can carry data (see
//! `CameraCommand` in `camera::types`).
//!
//! `pub(crate) const CONTROLS: &[(KnownCameraControl, &str)]` is a **slice
//! reference** to a **static array** — think of it like a Python tuple of tuples
//! that lives in the binary's read-only data section, not on the heap.  The `&`
//! is a reference (a borrowed pointer); in Python everything is a reference
//! implicitly, but Rust makes this explicit so the compiler can track lifetimes.

use anyhow::Result;
use nokhwa::utils::KnownCameraControl;

use crate::camera::CameraHandle;

// ── Controls exposed for keyboard adjustment ──────────────────────────

/// The nine camera controls selectable with keys 1–9.
///
/// Each entry is `(KnownCameraControl enum variant, human-readable name)`.
/// The index in this array maps directly to the number key (0 → key 1, etc.).
pub(crate) const CONTROLS: &[(KnownCameraControl, &str)] = &[
    (KnownCameraControl::Brightness, "Brightness"),
    (KnownCameraControl::Contrast, "Contrast"),
    (KnownCameraControl::Saturation, "Saturation"),
    (KnownCameraControl::Sharpness, "Sharpness"),
    (KnownCameraControl::Gain, "Gain"),
    (KnownCameraControl::WhiteBalance, "WhiteBalance"),
    (KnownCameraControl::Exposure, "Exposure"),
    (KnownCameraControl::Focus, "Focus"),
    (KnownCameraControl::Zoom, "Zoom"),
];

/// Select a control by index and print whether it is supported.
///
/// Does not send any command to the camera — just updates the UI selection.
/// Returns the index unchanged so the caller can update its local selection
/// variable.
pub(crate) fn select_control(index: usize, supported_controls: &[KnownCameraControl]) -> usize {
    let (control, name) = CONTROLS[index];
    if supported_controls.contains(&control) {
        println!("\nSelected: {name}");
    } else {
        println!("\n{name}: NOT supported by this camera.");
    }
    index
}

/// Print all current camera settings by sending a `GetControlInfo` command
/// for each supported control.
///
/// The results arrive asynchronously via the event channel — this function
/// only sends the requests.  The actual values are printed when the camera
/// thread responds (handled in the main loop's `CameraEvent::ControlInfo` arm).
///
/// Python analogy: this is like firing off multiple async requests and having
/// a separate callback handle each response.
pub(crate) fn print_all_settings(
    camera_handle: &CameraHandle,
    supported_controls: &[KnownCameraControl],
) -> Result<()> {
    println!("\n── Current Camera Settings ──");
    for &control in supported_controls {
        camera_handle.send_get_control_info(control);
    }
    println!();
    Ok(())
}

/// Print the keyboard shortcut reference and which controls are supported.
pub(crate) fn print_controls_help(supported_controls: &[KnownCameraControl]) {
    println!("\n── Keyboard Controls ──");
    println!("  q / Esc   Quit");
    println!("  r         Start / stop recording");
    println!("  s         Print all camera settings");
    println!("  ← / →     Rotate image 90°");
    println!("  1 - 9     Select a control to adjust");
    println!("  ↑ / ↓     Increase / decrease selected control");
    println!("\n── Available Controls ──");
    for (i, (control, name)) in CONTROLS.iter().enumerate() {
        let status = if supported_controls.contains(control) {
            "✓"
        } else {
            "✗"
        };
        println!("  {status}  {} = {name}", i + 1);
    }
    println!();
}
