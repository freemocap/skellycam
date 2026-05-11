//! VideoRecorder: spawns an ffmpeg subprocess per camera, pipes raw RGB frames
//! to ffmpeg's stdin for H.264 encoding. Handles metadata collection and cleanup.

pub struct VideoRecorder {}

impl VideoRecorder {
    pub fn new() -> Self {
        Self {}
    }
}
