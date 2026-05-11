//! On-screen status overlay bar.
//!
//! Draws a dark semi-transparent bar at the bottom of the frame with status
//! text: recording state, FPS, rotation angle, and the selected camera
//! control's name + value.
//!
//! ## How overlay rendering works
//!
//! 1. **Darken the bar area**: For each pixel in the bottom bar, blend the
//!    existing color 50/50 with a dark blue-grey `(0x10, 0x10, 0x20)`.  The
//!    `(old + 0x10) / 2` formula is an integer-approximation of alpha-blending
//!    — cheap, no floating point, and avoids overflow by casting to `u16`
//!    before adding.
//!
//! 2. **Build the status string**: Concatenate segments like `"REC:1234"`,
//!    `"60FPS"`, `"ROT:90"`, `"BRIGHTNESS:128"`, joined with `" | "`.
//!
//! 3. **Render text**: For each character, look up its 5×7 bitmap from the
//!    hard-coded font, scale each "pixel" to a `scale×scale` block of actual
//!    pixels, and write the foreground color (yellow `[240, 240, 80]`).
//!
//! ## Python / OpenCV analogy
//!
//! ```python
//! # Step 1: darken bar (cv2.addWeighted is more idiomatic but equivalent)
//! overlay = rgb[bar_top:, :].copy()
//! overlay = (overlay.astype(np.uint16) + 0x10) // 2
//! rgb[bar_top:, :] = overlay.astype(np.uint8)
//!
//! # Step 2 + 3: draw text at bottom
//! status = " | ".join(["REC:1234", "60FPS", "ROT:90"])
//! cv2.putText(rgb, status, (10, h - 10),
//!             cv2.FONT_HERSHEY_SIMPLEX, scale, (240, 240, 80))
//! ```
//!
//! The Rust version avoids OpenCV by working directly on the pixel buffer.
//! This is similar to how NumPy fancy-indexing lets you write pixels directly:
//! ```python
//! rgb[pixel_y, pixel_x] = (240, 240, 80)
//! ```

use image::RgbImage;

use super::font::{FONT, FONT_HEIGHT, FONT_WIDTH};

/// Info passed from main for the on-screen overlay bar.
///
/// All fields are cheap to move (stack-allocated primitives and a single
/// short `String`), so we pass by value.
pub struct OverlayState {
    pub recording: bool,
    pub frame_count: u64,
    pub frames_per_second: f64,
    /// 0, 90, 180, or 270
    pub rotation_degrees: u32,
    pub control_name: String,
    pub control_value: i64,
}

/// Draw a status bar at the bottom of the image.
///
/// Bar height and font scale are proportional to image height so the overlay
/// stays readable at any resolution (from 320×240 to 1920×1080).
///
/// The bar is drawn **directly onto** `image` — the pixel buffer is mutated
/// in place.  This is the Rust equivalent of modifying a `numpy.ndarray`
/// in-place rather than returning a new array.
pub fn draw_overlay(image: &mut RgbImage, state: &OverlayState) {
    let image_width = image.width();
    let image_height = image.height();
    // Bar height: ~1/30 of frame height, 18 px minimum
    let bar_height = (image_height / 30).max(18).min(image_height);
    let bar_y_position = image_height - bar_height;
    // Font scale: each "pixel" of the 5×7 font becomes a scale×scale block
    let font_scale = (bar_height / 13).max(1);

    // Dark semi-transparent background
    // Blend each pixel 50/50 with (0x10, 0x10, 0x20) — cheap alpha approximation.
    for y in bar_y_position..image_height {
        for x in 0..image_width {
            let pixel = image.get_pixel_mut(x, y);
            pixel[0] = ((pixel[0] as u16 + 0x10) / 2) as u8;
            pixel[1] = ((pixel[1] as u16 + 0x10) / 2) as u8;
            pixel[2] = ((pixel[2] as u16 + 0x20) / 2) as u8;
        }
    }

    // Build status text
    let mut parts: Vec<String> = Vec::new();
    if state.recording {
        parts.push(format!("REC:{}", state.frame_count));
    }
    parts.push(format!("{:.0}FPS", state.frames_per_second));
    parts.push(format!("ROT:{}", state.rotation_degrees));
    if !state.control_name.is_empty() {
        parts.push(format!(
            "{}:{}",
            state.control_name.to_uppercase(),
            state.control_value
        ));
    }
    let text = parts.join(" | ");

    // Center text vertically within the bar
    let text_height = FONT_HEIGHT * font_scale;
    let text_y_position = bar_y_position + (bar_height.saturating_sub(text_height)) / 2;

    draw_text_scaled(
        image,
        &text,
        6,
        text_y_position,
        font_scale,
        [240, 240, 80],
    );
}

/// Draw a string at `(x, y)` with each font pixel scaled to `scale×scale`.
///
/// Only supports ASCII 32–90 (space through 'Z').  Characters outside this
/// range render as '?'.
///
/// ## Algorithm
///
/// For each character in the string:
/// 1. Look up its glyph in the `FONT` table (5 columns × 7 rows of bits).
/// 2. For each column where the bit is set, paint a `scale×scale` block of
///    pixels in the specified color.
/// 3. Advance `x` by `FONT_WIDTH * scale` for the next character.
///
/// This is like `cv2.putText()` but with a fixed-pitch bitmap font and
/// nearest-neighbor upscaling (no anti-aliasing).
fn draw_text_scaled(
    image: &mut RgbImage,
    text: &str,
    mut x: u32,
    y: u32,
    scale: u32,
    color: [u8; 3],
) {
    for character in text.chars() {
        let glyph_index = if (32..=90).contains(&(character as u32)) {
            character as usize - 32
        } else {
            31 // '?' as fallback for unsupported characters
        };

        let glyph = &FONT[glyph_index];

        for column in 0..5u32 {
            let bits = glyph[column as usize];
            for row in 0..FONT_HEIGHT {
                if (bits >> row) & 1 != 0 {
                    for delta_y in 0..scale {
                        for delta_x in 0..scale {
                            let pixel_x = x + column * scale + delta_x;
                            let pixel_y = y + row * scale + delta_y;
                            if pixel_x < image.width() && pixel_y < image.height() {
                                let pixel = image.get_pixel_mut(pixel_x, pixel_y);
                                pixel[0] = color[0];
                                pixel[1] = color[1];
                                pixel[2] = color[2];
                            }
                        }
                    }
                }
            }
        }
        x += FONT_WIDTH * scale;
    }
}
