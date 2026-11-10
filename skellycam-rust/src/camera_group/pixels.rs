//! Tracker pixels: every camera image of one frameset decoded at full size, once, straight into memory the
//! caller owns (SkellyCam's shared-memory frame slots), cameras in parallel. BGR, sensor orientation: the
//! layout the OpenCV backend writes.

use super::dispatcher::RawFrame;
use super::jpeg::decode_bgr_into;

/// Decode each frame into its destination (`height * width * 3` bytes, BGR), cameras in parallel. `flags`:
/// see `jpeg::decode_bgr_into` (0 = exact).
pub fn decode_frameset_into(frames: &[RawFrame], destinations: Vec<&mut [u8]>, flags: i32) -> Result<(), String> {
    if frames.len() != destinations.len() {
        return Err(format!("{} frames but {} destinations", frames.len(), destinations.len()));
    }
    std::thread::scope(|scope| {
        let workers: Vec<_> = frames.iter()
            .zip(destinations)
            .map(|(frame, destination)| {
                scope.spawn(move || {
                    decode_bgr_into(&frame.jpeg_bytes, destination, frame.width, frame.height, flags)
                        .map_err(|error| format!("camera {}: {error}", frame.camera_id))
                })
            })
            .collect();
        workers.into_iter()
            .map(|worker| worker.join().unwrap_or_else(|_| Err("pixel worker panicked".into())))
            .collect::<Result<Vec<_>, _>>()
    })?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use image::RgbImage;

    use super::*;
    use crate::camera::FrameLifecycleTimestamps;
    use crate::camera_group::jpeg::encode_jpeg;

    fn frame(camera_id: &str, width: u32, height: u32) -> RawFrame {
        // Left half red, right half blue (RGB), at quality 95.
        let image = RgbImage::from_fn(width, height, |x, _| if x < width / 2 { image::Rgb([255, 0, 0]) } else { image::Rgb([0, 0, 255]) });
        RawFrame {
            camera_id: camera_id.into(),
            camera_index: 0,
            width,
            height,
            rotation: 0,
            jpeg_bytes: Arc::new(encode_jpeg(&image, 95).unwrap()),
            frame_number: 11,
            timestamps: FrameLifecycleTimestamps::new(),
        }
    }

    #[test]
    fn frames_decode_in_place_as_bgr_in_sensor_orientation() {
        let frames = [frame("a", 64, 48), frame("b", 32, 16)];
        let (mut first, mut second) = (vec![0u8; 64 * 48 * 3], vec![0u8; 32 * 16 * 3]);
        decode_frameset_into(&frames, vec![&mut first, &mut second], 0).unwrap();
        let pixel = |buffer: &[u8], width: usize, x: usize, y: usize| {
            let at = (y * width + x) * 3;
            (buffer[at], buffer[at + 1], buffer[at + 2])
        };
        let (blue, _, red) = pixel(&first, 64, 5, 24);
        assert!(red > 200 && blue < 60, "left of frame a should be red in BGR order");
        let (blue, _, red) = pixel(&second, 32, 28, 8);
        assert!(blue > 200 && red < 60, "right of frame b should be blue in BGR order");
    }

    #[test]
    fn a_destination_of_the_wrong_size_is_refused() {
        let frames = [frame("a", 64, 48)];
        let mut small = vec![0u8; 10];
        let error = decode_frameset_into(&frames, vec![&mut small], 0).unwrap_err();
        assert!(error.contains("camera a"), "{error}");
        assert!(decode_frameset_into(&frames, vec![], 0).is_err());
    }
}
