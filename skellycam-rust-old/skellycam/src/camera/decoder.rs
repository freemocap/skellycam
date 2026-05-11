//! Decoder thread: receives raw frames from the camera thread,
//! decodes them (MJPEG → RGB) using the `image` crate, timestamps
//! the decode operation, and sends decoded `FramePacket`s downstream.
//!
//! ## Why a separate decoder thread?
//!
//! Decoding MJPEG is CPU-intensive (~1-5ms per frame).  By moving it
//! off the camera thread, the camera thread stays thin: grab → timestamp
//! → send.  This minimises inter-camera grab timing spread in multi-camera
//! setups — all cameras grab in tight succession before any decoding begins.

use std::sync::mpsc;
use std::thread;

use super::types::{FramePacket, RawFrame};
use crate::timestamps::performance::performance_counter_nanoseconds;

/// Spawn a decoder thread.
///
/// Takes a `Receiver<RawFrame>` from the camera thread and returns a
/// `Receiver<FramePacket>` for the gatherer (or main thread) to consume.
///
/// The decoder thread exits when the camera thread drops its sender
/// (i.e., `raw_frame_receiver.recv()` returns `RecvError`).
pub fn spawn_decoder_thread(
    raw_frame_receiver: mpsc::Receiver<RawFrame>,
) -> mpsc::Receiver<FramePacket> {
    // sync_channel(1): backpressure from consumer to decoder.
    // If the consumer (gatherer) is slow, the decoder blocks here,
    // which in turn blocks the camera thread at its sync_channel send.
    let (decoded_sender, decoded_receiver) = mpsc::sync_channel::<FramePacket>(1);

    thread::spawn(move || {
        let mut frame_count: u64 = 0;
        let mut decode_failures: u64 = 0;

        loop {
            match raw_frame_receiver.recv() {
                Ok(raw_frame) => {
                    match image::load_from_memory(&raw_frame.raw_bytes) {
                        Ok(dynamic_image) => {
                            let decode_timestamp = performance_counter_nanoseconds();

                            let rgb_image = dynamic_image.to_rgb8();
                            let width = rgb_image.width();
                            let height = rgb_image.height();
                            let image_data = rgb_image.into_raw();

                            let packet = FramePacket {
                                image: image_data,
                                width,
                                height,
                                grab_timestamp_nanoseconds: raw_frame.grab_timestamp_nanoseconds,
                                decode_timestamp_nanoseconds: decode_timestamp,
                                identity: raw_frame.identity.clone(),
                                frame_number: raw_frame.frame_number,
                            };

                            frame_count += 1;

                            if decoded_sender.send(packet).is_err() {
                                tracing::info!(
                                    "Decoder exiting after {frame_count} frames (consumer disconnected)."
                                );
                                return;
                            }
                        }
                        Err(error) => {
                            decode_failures += 1;
                            if decode_failures <= 3 {
                                tracing::error!(
                                    "Failed to decode frame {} from {} ({} bytes): {error}",
                                    raw_frame.frame_number,
                                    raw_frame.identity.label(),
                                    raw_frame.raw_bytes.len()
                                );
                            } else if decode_failures % 100 == 1 {
                                tracing::warn!(
                                    "Failed to decode frame ({} total failures): {error}",
                                    decode_failures
                                );
                            }
                        }
                    }
                }
                Err(mpsc::RecvError) => {
                    tracing::info!(
                        "Decoder exiting after {frame_count} frames (camera disconnected)."
                    );
                    if decode_failures > 0 {
                        tracing::warn!("{decode_failures} frames failed to decode.");
                    }
                    return;
                }
            }
        }
    });

    decoded_receiver
}
