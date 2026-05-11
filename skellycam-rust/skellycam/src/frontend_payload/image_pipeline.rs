//! Image processing pipeline for frontend display frames.
//! Steps: rotate (if needed) → resize (50% or custom display size) → JPEG encode (quality 80).
//! Replaces Python's cv2.rotate + cv2.resize + cv2.imencode using the `image` crate.

pub struct ImagePipeline {}

impl ImagePipeline {
    pub fn new() -> Self {
        Self {}
    }
}
