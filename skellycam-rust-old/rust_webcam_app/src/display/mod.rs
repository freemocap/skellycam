//! Display module — window creation, overlay rendering, and bitmap font.
//!
//! ## Submodule layout
//!
//! - `window`: `DisplayWindow` wraps `minifb::Window` with RGB→ARGB conversion
//!   and split timing.
//! - `overlay`: Draws a status bar (recording indicator, FPS, rotation,
//!   control value) directly onto the frame's pixel buffer.
//! - `font`: A hard-coded 5×7 bitmap font covering ASCII 32–90 (space through
//!   'Z'), used by the overlay.
//!
//! ## Python / OpenCV analogy
//!
//! The display pipeline is:
//! ```python
//! # Convert RGB → ARGB (like cv2.cvtColor but with alpha channel)
//! argb = np.zeros((h, w), dtype=np.uint32)
//! argb[:] = (0xFF << 24) | (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
//!
//! # Draw overlay text directly on the image buffer
//! cv2.rectangle(rgb, (0, bar_top), (w, h), (0, 0, 0), -1)  # dark bar
//! cv2.putText(rgb, "60FPS | ROT:90", (10, h - 10), ...)
//! ```
//!
//! Instead of OpenCV's drawing functions, we manipulate pixel bytes directly.
//! This avoids pulling in a large dependency and gives full control over the
//! rendering.

mod font;
mod overlay;
mod window;

pub use overlay::{draw_overlay, OverlayState};
pub use window::DisplayWindow;
