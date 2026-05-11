//! CameraOrchestrator: the gatherer loop that implements structural backpressure.
//!
//! ## How lockstep synchronization works
//!
//! The gatherer calls `recv()` on every decoder's output channel in sequence.
//! Each `recv()` is **blocking** — it waits until that camera's decoder has produced
//! a frame.  Once ALL cameras have delivered a frame, the gatherer assembles a
//! `MultiFramePayload` and sends it downstream.
//!
//! This is structural backpressure:
//!
//! ```text
//! gatherer calls decoder_0.recv()  ← blocks until camera 0 has frame N
//! gatherer calls decoder_1.recv()  ← blocks until camera 1 has frame N
//!   → all cameras at frame N → emit MultiFramePayload { step: N }
//!   → decoders unblock → camera threads unblock → frame N+1 begins
//! ```
//!
//! No polling, no spin-wait, no `should_grab_by_id()`.  The channel topology
//! IS the synchronization mechanism.  A camera physically cannot advance to
//! frame N+1 until the gatherer has consumed frame N.

use std::sync::mpsc;
use std::thread;

use crate::camera::types::{FramePacket, MultiFramePayload};

/// Spawn a gatherer thread that implements structural backpressure lockstep.
///
/// Takes a vector of `Receiver<FramePacket>` (one per camera's decoder output)
/// and returns a `Receiver<MultiFramePayload>` for the main thread to consume.
///
/// The gatherer exits when any decoder channel disconnects (camera shutdown).
pub fn spawn_gatherer(
    decoder_receivers: Vec<mpsc::Receiver<FramePacket>>,
) -> mpsc::Receiver<MultiFramePayload> {
    let (sender, receiver) = mpsc::sync_channel::<MultiFramePayload>(1);

    let number_of_cameras = decoder_receivers.len();

    thread::spawn(move || {
        let mut step: i64 = 0;

        loop {
            let mut frames = Vec::with_capacity(number_of_cameras);

            // Block on each decoder in sequence.
            // This IS the synchronization — no camera can be at frame N+1
            // until all cameras have delivered frame N.
            for receiver in &decoder_receivers {
                match receiver.recv() {
                    Ok(frame) => frames.push(frame),
                    Err(_) => {
                        tracing::info!(
                            "Gatherer exiting at step {step}: a decoder disconnected."
                        );
                        return;
                    }
                }
            }

            let payload = MultiFramePayload {
                frames,
                step,
            };

            if sender.send(payload).is_err() {
                // Consumer disconnected — shut down.
                tracing::info!("Gatherer exiting at step {step}: consumer disconnected.");
                return;
            }

            step += 1;
        }
    });

    receiver
}
