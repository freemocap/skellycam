//! Image pipeline: resize, rotate, and JPEG-encode RGB frames for the
//! frontend WebSocket payload.
//!
//! The `image` crate handles all pixel operations. Input is always 24-bit
//! RGB (3 bytes per pixel, as produced by openpnp-capture). Output is a
//! JPEG byte vector.

/// Default JPEG quality (0-100, where 80 is a good balance of size vs quality).
pub const DEFAULT_JPEG_QUALITY: u8 = 80;

/// Default scale factor for frontend display (50% of original).
pub const DEFAULT_DISPLAY_SCALE: f32 = 0.5;

/// JPEG-encode an RGB byte buffer at the given quality.
///
/// `rgb_data` must be `width * height * 3` bytes of 24-bit RGB pixel data.
/// Returns the JPEG-encoded bytes.
pub fn jpeg_encode_rgb(
    rgb_data: &[u8],
    width: u32,
    height: u32,
    quality: u8,
) -> Result<Vec<u8>, String> {
    let img = image::RgbImage::from_raw(width, height, rgb_data.to_vec())
        .ok_or("Failed to create RgbImage from raw data")?;

    let mut jpeg_bytes: Vec<u8> = Vec::new();
    let mut encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut jpeg_bytes, quality);
    encoder
        .encode(
            &image::DynamicImage::ImageRgb8(img).to_rgb8(),
            width,
            height,
            image::ExtendedColorType::Rgb8,
        )
        .map_err(|e| format!("JPEG encode error: {e}"))?;

    Ok(jpeg_bytes)
}

/// Resize an RGB image by a scale factor.
///
/// Uses `image::imageops::resize` with `FilterType::Triangle` (bilinear-ish,
/// fast, good for downscaling).
/// Returns a new `Vec<u8>` with the resized RGB pixel data and the new dimensions.
pub fn resize_rgb(
    rgb_data: &[u8],
    width: u32,
    height: u32,
    scale: f32,
) -> (Vec<u8>, u32, u32) {
    let new_w = (width as f32 * scale) as u32;
    let new_h = (height as f32 * scale) as u32;

    if new_w < 1 || new_h < 1 {
        return (Vec::new(), 0, 0);
    }

    let img = match image::RgbImage::from_raw(width, height, rgb_data.to_vec()) {
        Some(i) => i,
        None => return (Vec::new(), width, height),
    };

    let resized = image::imageops::resize(
        &img,
        new_w,
        new_h,
        image::imageops::FilterType::Triangle,
    );

    (resized.into_raw(), new_w, new_h)
}

/// Rotate an RGB image 90 degrees clockwise.
///
/// Returns the rotated pixel data and new (width, height).
pub fn rotate_90_clockwise(
    rgb_data: &[u8],
    width: u32,
    height: u32,
) -> (Vec<u8>, u32, u32) {
    let img = match image::RgbImage::from_raw(width, height, rgb_data.to_vec()) {
        Some(i) => i,
        None => return (Vec::new(), width, height),
    };

    let rotated = image::imageops::rotate90(&img);
    let new_w = rotated.width();
    let new_h = rotated.height();
    (rotated.into_raw(), new_w, new_h)
}
