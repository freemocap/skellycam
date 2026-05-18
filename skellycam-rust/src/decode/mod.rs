//! On-demand JPEG-to-RGB decode utilities.
//!
//! All decoding is opt-in — the camera hot loop never touches these
//! functions. Call them from tests, the PyO3 bridge, or any downstream
//! consumer that needs raw pixel access.

/// Decode MJPEG bytes to raw 24-bit RGB pixels.
///
/// Returns `(width, height, rgb_pixels)` where `rgb_pixels` is
/// `width * height * 3` bytes in row-major RGB order.
///
/// Uses the `image` crate's JPEG decoder. Caller pays the decode cost
/// on demand — this is never called on the camera hot path.
pub fn mjpeg_to_rgb(jpeg_bytes: &[u8]) -> anyhow::Result<(u32, u32, Vec<u8>)> {
    let img = image::load_from_memory(jpeg_bytes)
        .map_err(|e| anyhow::anyhow!("JPEG decode failed: {e}"))?;
    let rgb = img.to_rgb8();
    let (w, h) = rgb.dimensions();
    Ok((w, h, rgb.into_raw()))
}

/// Compute ITU-R BT.601 luminance from raw RGB pixels.
///
/// RGB is 3 bytes per pixel (R, G, B). Returns mean luminance 0–255.
///
/// # Why not just `(R + G + B) / 3`?
///
/// Human eyes have far more green-sensitive cone cells than red or blue.
/// A purely green light looks much brighter than a purely blue light of the
/// same physical intensity. The naive mean treats all channels equally and
/// misrepresents perceived brightness.
///
/// The ITU-R BT.601 standard (1982, "Broadcasting service — Television")
/// defines luminance weights matched to CRT phosphor characteristics and
/// human cone cell sensitivity:
///
///   Y = 0.299·R + 0.587·G + 0.114·B
///
/// Green dominates at 58.7%, red at 29.9%, blue at 11.4%. This is the
/// standard luma calculation used in every JPEG encoder, video codec, and
/// television broadcast since the 1980s.
pub fn mean_luminance(rgb: &[u8]) -> f64 {
    if rgb.len() < 3 {
        return 0.0;
    }
    let sum: f64 = rgb
        .chunks_exact(3)
        .map(|p| 0.299 * p[0] as f64 + 0.587 * p[1] as f64 + 0.114 * p[2] as f64)
        .sum();
    sum / (rgb.len() / 3) as f64
}