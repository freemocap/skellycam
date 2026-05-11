//! Display window wrapper around `minifb`.
//!
//! Manages the on-screen window, keyboard input collection, and the RGB→ARGB
//! conversion needed to push frames to the display.
//!
//! ## Why ARGB?
//!
//! `minifb` expects a `Vec<u32>` where each `u32` is `0xAARRGGBB` (alpha in
//! the high byte, then red, green, blue).  Our frames arrive as `Vec<u8>` in
//! RGB order (3 bytes per pixel, no alpha).  The conversion packs three `u8`
//! channels into one `u32`, setting alpha to `0xFF` (fully opaque).
//!
//! ## Python / NumPy analogy
//!
//! The RGB→ARGB conversion is:
//! ```python
//! # rgb: np.ndarray of shape (pixel_count, 3), dtype=np.uint8
//! argb = (0xFF000000
//!         | (rgb[:, 0].astype(np.uint32) << 16)
//!         | (rgb[:, 1].astype(np.uint32) << 8)
//!         | rgb[:, 2].astype(np.uint32))
//! ```
//!
//! In NumPy this is vectorized — the whole array is processed in C.  In Rust,
//! we write the loop explicitly, but the compiler auto-vectorizes it to SIMD
//! instructions.  The `unsafe` block with raw pointers gives the compiler
//! enough information to optimize aggressively.
//!
//! ## Why `unsafe` in `show()`?
//!
//! The Rust compiler's auto-vectorization (converting scalar loops to SIMD)
//! works best when it can see the entire access pattern.  Using raw pointers
//! (`source.add(offset)`, `destination.add(i)`) rather than iterators or
//! indexing lets LLVM prove there's no aliasing between the source and
//! destination slices, which is a prerequisite for vectorization.
//!
//! The `unsafe` block is auditable: the loop bounds are computed from the
//! slice lengths, so no out-of-bounds access can occur.  This is the same
//! tradeoff as using a C extension in Python — you give up safety guarantees
//! for performance, but in Rust the unsafe region is explicitly marked and
//! can be reviewed in isolation.

use anyhow::{Context, Result};
use image::RgbImage;
use minifb::{Key, Window, WindowOptions};

/// Simple display window that shows webcam frames using `minifb`.
///
/// `minifb` ("mini frame buffer") is a cross-platform windowing library that
/// gives you a raw pixel buffer to push frames to.  It's like a minimal
/// `SDL_Window` or `glfw` window, but you just push bytes — no OpenGL context
/// needed.  For Python users, think of it as a replacement for
/// `cv2.imshow("window", frame)` that gives you finer control over timing and
/// pixel format.
pub struct DisplayWindow {
    window: Window,
    /// Pre-allocated ARGB buffer (one `u32` per pixel).  Reused across frames
    /// to avoid allocation — this is the Rust equivalent of
    /// `self.buffer = np.empty((h*w,), dtype=np.uint32)` initialized once.
    buffer: Vec<u32>,
    /// Accumulated pressed keys since last poll.  Cleared each frame by
    /// `collect_keys()`, then re-populated.  Like calling `cv2.waitKey(1)`
    /// repeatedly until no more keys are queued.
    keys_down: Vec<Key>,
    /// Nanoseconds spent in RGB→ARGB conversion for the most recent frame.
    pub last_conversion_nanoseconds: u128,
    /// Nanoseconds spent in `update_with_buffer` for the most recent frame.
    pub last_buffer_update_nanoseconds: u128,
}

impl DisplayWindow {
    /// Create a new window with the given dimensions and title.
    ///
    /// `Scale::FitScreen` tells minifb to scale the content to fit the window
    /// while preserving aspect ratio (letterboxing).  This is like OpenCV's
    /// `cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO`.
    ///
    /// `set_target_fps(0)` disables minifb's internal frame-rate limiting —
    /// we control timing ourselves in the main loop.
    pub fn new(width: u32, height: u32, title: &str) -> Result<Self> {
        let buffer = vec![0u32; (width * height) as usize];
        let mut window = Window::new(
            title,
            width as usize,
            height as usize,
            WindowOptions {
                resize: true,
                scale: minifb::Scale::FitScreen,
                ..WindowOptions::default()
            },
        )
        .context("Failed to create display window.")?;

        window.set_target_fps(0); // unlimited — we control timing

        Ok(Self {
            window,
            buffer,
            keys_down: Vec::new(),
            last_conversion_nanoseconds: 0,
            last_buffer_update_nanoseconds: 0,
        })
    }

    /// Recreate the window with new dimensions.
    ///
    /// Called when rotation or scaling changes the frame size.  minifb doesn't
    /// support resizing its pixel buffer in-place, so we tear down and recreate.
    ///
    /// The old `Window` is dropped (closed) here, and a new one opens.  There
    /// may be a brief flicker — this is acceptable for a learning project.
    /// A production app would use a resizable graphics API (wgpu, OpenGL).
    pub fn update_dimensions(&mut self, width: u32, height: u32, title: &str) -> Result<()> {
        self.buffer = vec![0u32; (width * height) as usize];
        let mut window = Window::new(
            title,
            width as usize,
            height as usize,
            WindowOptions {
                resize: true,
                scale: minifb::Scale::FitScreen,
                ..WindowOptions::default()
            },
        )
        .context("Failed to recreate display window after resize.")?;
        window.set_target_fps(0);
        self.window = window;
        Ok(())
    }

    /// Change the window title (e.g., to show recording status).
    pub fn set_title(&mut self, title: &str) {
        self.window.set_title(title);
    }

    /// Convert an RGB image to the internal ARGB buffer, then push to the window.
    ///
    /// Times the conversion and buffer-update stages separately and stores them
    /// in `last_conversion_nanoseconds` / `last_buffer_update_nanoseconds`.
    ///
    /// ## The two-stage pipeline
    ///
    /// **Stage 1 — RGB→ARGB conversion**: Reads `&[u8]` (3 bytes per pixel),
    /// writes `&mut [u32]` (1 `u32` per pixel).  Uses unsafe raw pointer
    /// indexing for auto-vectorization.
    ///
    /// **Stage 2 — minifb buffer update**: Pushes the ARGB buffer to the GPU
    /// for display.  This is where vsync latency lives.
    ///
    /// Returns `true` if the window is still open after the update.
    pub fn show(&mut self, image: &RgbImage) -> bool {
        let raw_bytes = image.as_raw();
        let pixel_count = raw_bytes.len() / 3;
        assert_eq!(pixel_count, self.buffer.len());

        // ── Stage 1: RGB → ARGB conversion ──────────────────────────
        //
        // Uses raw pointers instead of `chunks_exact(3).zip(...)` so the
        // compiler can auto-vectorise the loop over the full pixel count.
        let conversion_start = std::time::Instant::now();
        unsafe {
            let source = raw_bytes.as_ptr();
            let destination = self.buffer.as_mut_ptr();
            for i in 0..pixel_count {
                let offset = i * 3;
                let red = *source.add(offset);
                let green = *source.add(offset + 1);
                let blue = *source.add(offset + 2);
                *destination.add(i) =
                    0xFF00_0000 | ((red as u32) << 16) | ((green as u32) << 8) | (blue as u32);
            }
        }
        self.last_conversion_nanoseconds = conversion_start.elapsed().as_nanos();

        // ── Stage 2: minifb buffer update ───────────────────────────
        let update_start = std::time::Instant::now();
        let result = self.window.update_with_buffer(
            &self.buffer,
            image.width() as usize,
            image.height() as usize,
        );
        self.last_buffer_update_nanoseconds = update_start.elapsed().as_nanos();

        result.is_ok() && self.window.is_open()
    }

    /// Returns the split timing from the most recent `show()` call:
    /// `(conversion_nanoseconds, buffer_update_nanoseconds)`.
    pub fn last_timing(&self) -> (u128, u128) {
        (self.last_conversion_nanoseconds, self.last_buffer_update_nanoseconds)
    }

    /// Collect all keys pressed since the last poll.
    ///
    /// Clears the internal buffer and re-populates from minifb.  Returns a
    /// slice so the caller can `for key in display.collect_keys()` without
    /// an extra copy.
    ///
    /// Python analogy: `keys = [cv2.waitKey(1) for _ in range(n)]` loop
    /// equivalent.
    pub fn collect_keys(&mut self) -> &[Key] {
        self.keys_down.clear();
        self.window
            .get_keys_pressed(minifb::KeyRepeat::No)
            .iter()
            .for_each(|&key| self.keys_down.push(key));
        &self.keys_down
    }

    /// Check if the window is still open (user hasn't clicked the close button).
    pub fn is_open(&self) -> bool {
        self.window.is_open()
    }
}
