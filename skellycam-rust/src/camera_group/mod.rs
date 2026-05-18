pub mod types;
pub mod camera_group;
pub mod gatherer;
pub mod dispatcher;
pub mod sync_utils;
pub mod frontend_encoder;
pub mod jpeg_transform;
pub mod recording_stats;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::time::Duration;

use crate::camera::MultiFramePayload;

pub use types::{CameraGroupConfig, DispatcherCommand, GathererUpdate, RecordingParams};
pub use camera_group::{
    CameraGroup, CameraGroupState, CameraStatus, GathererInvalidTransition,
    GathererState, GathererStateMachine, GathererTimestamps,
};
pub use dispatcher::FrontendPayload;
pub use frontend_encoder::{encode_multiframe, encode_payload, FrameHeader, PayloadHeader};
pub use jpeg_transform::rotate_jpeg_lossless;

/// Block on `receiver` until `shutdown` is set or the channel disconnects.
///
/// Calls `on_frame` for each `MultiFramePayload` received. If `on_frame`
/// returns `false`, the loop stops early — used by time-limited or
/// frame-count-limited recording sessions.
///
/// All five pipeline consumers (HTTP relay, PyO3 bridge, CLI test harness
/// paths) use this single function instead of maintaining independent
/// copies of the same loop.
pub fn consume_multiframe_loop<F>(
    receiver: &mpsc::Receiver<MultiFramePayload>,
    shutdown: &AtomicBool,
    timeout_ms: u64,
    mut on_frame: F,
) where
    F: FnMut(MultiFramePayload) -> bool,
{
    while !shutdown.load(Ordering::SeqCst) {
        match receiver.recv_timeout(Duration::from_millis(timeout_ms)) {
            Ok(payload) => {
                if !on_frame(payload) {
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
}
