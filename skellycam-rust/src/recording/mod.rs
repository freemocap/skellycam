pub mod finalizer;
pub mod recorder;
pub mod recording_thread;

pub use finalizer::finalize_recording;
pub use recorder::{FrameTimestamp, RecorderSpawnConfig, VideoRecorder, VideoRecorderConfig};
pub use recording_thread::{RecordingFrameData, RecordingHandle, spawn_recording_thread};
