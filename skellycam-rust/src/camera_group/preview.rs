//! UI preview images, built on request from the newest frameset.
//!
//! Same contract as SkellyCam's Python `create_frontend_payload`: rotate each camera image,
//! scale it to the UI's display size but never above half the camera resolution, encode JPEG at
//! quality 60, and pack the frameset in the shared wire layout. Cameras are built in parallel.
//! libjpeg-turbo decodes each camera JPEG with DCT scaling (1/2, 1/4 or 1/8), so the decode cost
//! follows the preview size; only the small image is rotated and resized.

use std::collections::HashMap;

use image::imageops;

use super::dispatcher::{FrontendPayload, RawFrame};
use super::frontend_encoder::{pack_payload, PreviewImage};
use super::jpeg::{decode_scaled, encode_jpeg};

/// Largest preview relative to the camera image, as in the Python encoder.
pub const MAX_PREVIEW_SCALE: f64 = 0.5;
/// Preview JPEG quality, as in the Python encoder's `JPEG_ENCODING_PARAMETERS`.
pub const PREVIEW_JPEG_QUALITY: i32 = 60;

/// Image size after SkellyCam's rotation codes (OpenCV `cv2.rotate`: 0 = 90° clockwise,
/// 1 = 180°, 2 = 90° counterclockwise, -1 = none).
pub fn rotated_size(width: u32, height: u32, rotation: i32) -> (u32, u32) {
    if matches!(rotation, 0 | 2) { (height, width) } else { (width, height) }
}

/// Preview size: the Python encoder's formula, applied to the rotated camera image.
pub fn preview_size(width: u32, height: u32, rotation: i32, display: Option<(u32, u32)>) -> (u32, u32) {
    let (width, height) = rotated_size(width, height, rotation);
    let mut scale = MAX_PREVIEW_SCALE;
    if let Some((display_width, display_height)) = display {
        scale = scale.min(display_width as f64 / width as f64).min(display_height as f64 / height as f64);
    }
    ((width as f64 * scale) as u32, (height as f64 * scale) as u32)
}

/// Largest DCT scaling denominator whose decoded image still covers the preview size.
fn decode_denominator(rotated: (u32, u32), preview: (u32, u32)) -> u32 {
    [8, 4, 2].into_iter()
        .find(|&denominator| rotated.0.div_ceil(denominator) >= preview.0 && rotated.1.div_ceil(denominator) >= preview.1)
        .unwrap_or(1)
}

/// One camera's preview: scaled decode, rotate, resize to the preview size, JPEG q60.
pub fn preview_image(frame: &RawFrame, display: Option<(u32, u32)>) -> Result<PreviewImage, String> {
    let label = |error: String| format!("camera {}: {error}", frame.camera_id);
    let rotated = rotated_size(frame.width, frame.height, frame.rotation);
    let (width, height) = preview_size(frame.width, frame.height, frame.rotation, display);
    if width < 1 || height < 1 {
        return Err(label("Image dimensions must be positive".to_string()));
    }
    let decoded = decode_scaled(&frame.jpeg_bytes, decode_denominator(rotated, (width, height))).map_err(label)?;
    let upright = match frame.rotation {
        0 => imageops::rotate90(&decoded),
        1 => imageops::rotate180(&decoded),
        2 => imageops::rotate270(&decoded),
        _ => decoded,
    };
    let sized = if upright.dimensions() == (width, height) {
        upright
    } else {
        imageops::resize(&upright, width, height, imageops::FilterType::Triangle)
    };
    Ok(PreviewImage {
        camera_id: frame.camera_id.clone(),
        camera_index: frame.camera_index,
        width,
        height,
        jpeg: encode_jpeg(&sized, PREVIEW_JPEG_QUALITY).map_err(label)?,
    })
}

/// The wire payload for one frameset, cameras built in parallel.
///
/// `display_sizes` maps camera IDs to the UI's display size; cameras without one get half size.
/// The timestamp is the mean of each camera's main timestamp (midpoint of the frame-grab bracket).
pub fn build_frontend_payload(
    frames: &[RawFrame],
    display_sizes: &HashMap<String, (u32, u32)>,
    camera_fps: f64,
) -> Result<FrontendPayload, String> {
    let Some(first) = frames.first() else { return Err("Cannot serialize an empty image group".into()) };
    if frames.iter().any(|frame| frame.frame_number != first.frame_number) {
        return Err("Camera frame numbers must agree".into());
    }
    let images = std::thread::scope(|scope| {
        let workers: Vec<_> = frames.iter()
            .map(|frame| {
                let display = display_sizes.get(&frame.camera_id).copied();
                scope.spawn(move || preview_image(frame, display))
            })
            .collect();
        workers.into_iter()
            .map(|worker| worker.join().unwrap_or_else(|_| Err("preview worker panicked".into())))
            .collect::<Result<Vec<_>, _>>()
    })?;
    let timestamp_ns = frames.iter()
        .map(|frame| (frame.timestamps.loop_start_ns as f64 + frame.timestamps.frame_available_ns as f64) / 2.0)
        .sum::<f64>() / frames.len() as f64;
    Ok(FrontendPayload {
        frame_number: first.frame_number,
        timestamp_ns,
        camera_fps,
        jpeg_bytes: pack_payload(first.frame_number, &images)?,
    })
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use image::RgbImage;

    use super::*;
    use crate::camera::FrameLifecycleTimestamps;
    use crate::camera_group::jpeg::{decode_scaled, encode_jpeg};

    fn camera_jpeg(width: u32, height: u32) -> Vec<u8> {
        // Left half red, right half blue, so rotations are distinguishable after decoding.
        let image = RgbImage::from_fn(width, height, |x, _| if x < width / 2 { image::Rgb([255, 0, 0]) } else { image::Rgb([0, 0, 255]) });
        encode_jpeg(&image, 95).unwrap()
    }

    fn raw_frame(camera_id: &str, rotation: i32, jpeg: Vec<u8>, width: u32, height: u32) -> RawFrame {
        let mut timestamps = FrameLifecycleTimestamps::new();
        timestamps.loop_start_ns = 100;
        timestamps.frame_available_ns = 300;
        RawFrame {
            camera_id: camera_id.into(),
            camera_index: 2,
            width,
            height,
            rotation,
            jpeg_bytes: Arc::new(jpeg),
            frame_number: 7,
            timestamps,
        }
    }

    fn decode_full(jpeg: &[u8]) -> RgbImage {
        decode_scaled(jpeg, 1).unwrap()
    }

    #[test]
    fn preview_size_follows_the_python_formula() {
        // scale = min(display_w / w, display_h / h, 0.5) on the rotated image, truncated.
        assert_eq!(preview_size(1280, 720, -1, None), (640, 360));
        assert_eq!(preview_size(1280, 720, 0, None), (360, 640));
        assert_eq!(preview_size(1280, 720, 1, Some((1000, 1000))), (640, 360));
        assert_eq!(preview_size(1280, 720, -1, Some((300, 1000))), (300, 168));
        assert_eq!(preview_size(1280, 720, 2, Some((1000, 333))), (187, 333));
    }

    #[test]
    fn decode_denominator_keeps_the_decode_at_least_preview_size() {
        assert_eq!(decode_denominator((1280, 720), (640, 360)), 2);
        assert_eq!(decode_denominator((1280, 720), (300, 168)), 4);
        assert_eq!(decode_denominator((1280, 720), (160, 90)), 8);
        assert_eq!(decode_denominator((1280, 720), (161, 90)), 4);
    }

    #[test]
    fn each_rotation_turns_the_image_upright_at_preview_size() {
        let jpeg = camera_jpeg(320, 240);
        for (rotation, size, red_at) in [(-1, (160, 120), (10, 60)), (0, (120, 160), (60, 10)),
                                         (1, (160, 120), (150, 60)), (2, (120, 160), (60, 150))] {
            let preview = preview_image(&raw_frame("cam", rotation, jpeg.clone(), 320, 240), None).unwrap();
            assert_eq!((preview.width, preview.height), size, "rotation {rotation}");
            let image = decode_full(&preview.jpeg);
            assert_eq!(image.dimensions(), size, "rotation {rotation}");
            let pixel = image.get_pixel(red_at.0, red_at.1);
            assert!(pixel[0] > 200 && pixel[2] < 60, "rotation {rotation}: expected red at {red_at:?}, got {pixel:?}");
        }
    }

    #[test]
    fn payload_has_the_shared_wire_layout() {
        let frames = [raw_frame("abcd", -1, camera_jpeg(320, 240), 320, 240),
                      raw_frame("ef01", 0, camera_jpeg(320, 240), 320, 240)];
        let sizes = HashMap::from([("ef01".to_string(), (60, 1000))]);
        let payload = build_frontend_payload(&frames, &sizes, 30.0).unwrap();
        assert_eq!((payload.frame_number, payload.timestamp_ns), (7, 200.0));
        let bytes = &payload.jpeg_bytes;
        assert_eq!((bytes[0], i64::from_le_bytes(bytes[8..16].try_into().unwrap()),
                    i32::from_le_bytes(bytes[16..20].try_into().unwrap())), (0, 7, 2));
        let mut offset = 24;
        for (camera_id, size) in [("abcd", (160, 120)), ("ef01", (60, 80))] {
            let header = &bytes[offset..offset + 56];
            assert_eq!(header[0], 1);
            assert_eq!(&header[16..16 + camera_id.len()], camera_id.as_bytes());
            let field = |at: usize| i32::from_le_bytes(header[at..at + 4].try_into().unwrap());
            assert_eq!((field(32), field(36), field(40), field(44)), (2, size.0, size.1, 3));
            let length = field(48) as usize;
            assert_eq!(decode_full(&bytes[offset + 56..offset + 56 + length]).dimensions(), (size.0 as u32, size.1 as u32));
            offset += 56 + length;
        }
        assert_eq!((bytes[offset], bytes.len()), (2, offset + 24));
    }

    #[test]
    fn invalid_frames_are_refused_like_the_python_encoder() {
        let jpeg = camera_jpeg(64, 48);
        assert!(build_frontend_payload(&[], &HashMap::new(), 0.0).is_err());
        let mut late = raw_frame("b", -1, jpeg.clone(), 64, 48);
        late.frame_number = 8;
        assert!(build_frontend_payload(&[raw_frame("a", -1, jpeg.clone(), 64, 48), late], &HashMap::new(), 0.0).is_err());
        let tiny = HashMap::from([("a".to_string(), (0, 10))]);
        assert!(build_frontend_payload(&[raw_frame("a", -1, jpeg.clone(), 64, 48)], &tiny, 0.0).is_err());
        assert!(build_frontend_payload(&[raw_frame("seventeen-chars-x", -1, jpeg, 64, 48)], &HashMap::new(), 0.0).is_err());
    }
}
