//! Legacy image pipeline utilities — RGB resize and JPEG encode.
//!
//! Most camera frames are MJPEG and flow through the camera_group dispatcher
//! directly. These RGB utilities are a fallback for non-MJPEG cameras.
//! Primary frontend encoding now lives in `camera_group::frontend_encoder`.

pub mod image_pipeline;

pub use image_pipeline::{jpeg_encode_rgb, resize_rgb, DEFAULT_DISPLAY_SCALE, DEFAULT_JPEG_QUALITY};
