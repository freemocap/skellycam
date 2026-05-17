pub mod finalizer;
pub mod recorder;

pub use finalizer::finalize_recording;
pub use recorder::{FrameTimestamp, VideoRecorder, VideoRecorderConfig};
