pub mod types;
pub mod gatherer;
pub mod state_machine;
pub mod sync_utils;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::time::Duration;

use crate::camera::MultiFramePayload;

pub use types::CameraGroupConfig;
pub use state_machine::{
    CameraGroup, CaptureState, Empty, GathererState, GathererStateMachine, RecordingState,
    Streaming,
};

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
    while shutdown.load(Ordering::SeqCst) {
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
