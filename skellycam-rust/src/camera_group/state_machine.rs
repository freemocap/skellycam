//! CameraGroup state machine — compile-time-enforced lifecycle states for a
//! synchronized group of `Camera` instances.
//!
//! ## Design
//!
//! A `CameraGroup` manages N cameras (N >= 1) synchronized through a shared
//! `BreakableBarrier`. The group is the top-level citizen — a single-camera
//! setup is just a group with one camera, using the same API and state machine.
//!
//! Top-level states use the Hoverbear Approach 3 pattern: `CameraGroup<S>` is
//! generic over the state type `S`. Recording and Paused live at the group
//! level because they define gatherer behavior, not individual camera behavior.
//!
//! The `Streaming` state carries three orthogonal runtime regions:
//! - **Capture**: Active or Paused (gatherer controls barrier release)
//! - **Recording**: NotRecording or Recording (gatherer writes to disk)
//! - **Gatherer**: the gatherer's internal frame cycle, tracked by
//!   `GathererStateMachine` with automatic timestamp recording
//!
//! ## State diagram
//!
//! See `docs/state_machines/camera_group_state_machine.md` for the Mermaid diagram.

use std::sync::mpsc;
use std::sync::Arc;
use std::thread::JoinHandle;

use crate::camera::Camera;
use crate::camera::Configuring as CameraConfiguring;
use crate::camera::Streaming as CameraStreaming;
use crate::camera_group::sync_utils::BreakableBarrier;
use crate::timestamps::performance::performance_counter_nanoseconds;

use super::types::CameraGroupConfig;

// ── Top-level state marker types ────────────────────────────────────────────

/// No configs, no cameras, nothing allocated.
#[derive(Debug)]
pub struct Empty;

/// Configs loaded, cameras enumerated, but nothing running.
#[derive(Debug)]
pub struct Configured {
    pub configs: Vec<CameraGroupConfig>,
}

/// All cameras streaming, gatherer running, frames flowing.
///
/// `camera_handles` stores the command sender, identity, and config for each
/// camera — enough to send shutdown commands and report status. The actual
/// `Camera<Streaming>` instances are destructured during startup: their
/// receivers are given to the gatherer, and their thread handles are stored
/// here for joining on shutdown.
///
/// Orthogonal runtime regions within Streaming:
/// - `capture_state`: Active or Paused
/// - `recording_state`: NotRecording or Recording
///
/// The `GathererStateMachine` lives inside the gatherer thread (same pattern
/// as `FrameStateMachine` in the camera thread). Gatherer timestamps flow
/// out via each `MultiFramePayload`.
#[derive(Debug)]
pub struct Streaming {
    pub camera_handles: Vec<crate::camera::CameraHandle>,
    pub camera_thread_handles: Vec<JoinHandle<()>>,
    pub gatherer_handle: JoinHandle<()>,
    pub multi_frame_receiver: mpsc::Receiver<MultiFramePayload>,
    pub barrier: Arc<BreakableBarrier>,
    pub capture_state: CaptureState,
    pub recording_state: RecordingState,
}

/// Shutdown initiated. Camera threads and gatherer are unwinding.
#[derive(Debug)]
pub struct ShuttingDown {
    pub camera_thread_handles: Vec<JoinHandle<()>>,
    pub gatherer_handle: JoinHandle<()>,
}

/// All threads joined, all resources freed. Terminal state.
#[derive(Debug)]
pub struct Stopped;

// ── The machine ─────────────────────────────────────────────────────────────

/// A group of synchronized cameras whose current lifecycle state is encoded
/// in the type parameter `S`.
///
/// # Type-state enforcement
///
/// Methods that transition between states consume `self` and return a new
/// `CameraGroup` with a different `S`. Invalid transitions are compile errors.
///
/// ```compile_fail
/// # use skellycam::camera_group::state_machine::*;
/// let group = CameraGroup::<Empty>::new();
/// group.pause(); // COMPILE ERROR: method not found for `CameraGroup<Empty>`
/// ```
#[derive(Debug)]
pub struct CameraGroup<S> {
    pub group_id: String,
    pub state: S,
}

// ── Runtime orthogonal regions within Streaming ─────────────────────────────

/// Whether the capture cycle is actively producing frames.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CaptureState {
    /// Gatherer releases barrier normally; cameras capture in lockstep.
    Active,
    /// Gatherer does NOT enter barrier; all cameras block at
    /// `barrier.wait()` in their `AtBarrier` substate.
    Paused,
}

/// Whether frames are being written to disk.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RecordingState {
    /// Frames forwarded downstream only (WebSocket / PyO3 bridge).
    NotRecording,
    /// Frames forwarded downstream AND written to disk via recording module.
    Recording,
}

// ── GathererStateMachine ────────────────────────────────────────────────────

/// High-frequency states of the gatherer's internal frame cycle.
///
/// Every transition automatically records a nanosecond-precision monotonic
/// timestamp. These timestamps populate the `MultiFramePayload`'s gatherer-level
/// fields.
///
/// Cycle order (post-fix): `CollectingFrames → AllFramesReceived → WaitingAtBarrier
/// → AssemblingPayload → SendingDownstream → CollectingFrames`. The barrier
/// fires the moment the last frame arrives, releasing all cameras to begin
/// their next capture spin in parallel with the gatherer's payload work.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GathererState {
    /// Receiving one `FramePacket` from each camera. Blocking on
    /// `frame_receiver.recv()` in sequence.
    CollectingFrames,
    /// All frames received. Marker state immediately before entering the
    /// barrier — no per-cycle work happens here.
    AllFramesReceived,
    /// Blocked at `BreakableBarrier::wait()`, synchronized with all cameras.
    /// When this releases, all cameras and the gatherer continue together.
    WaitingAtBarrier,
    /// Barrier released; building the `MultiFramePayload` struct. Cameras are
    /// now spinning for their next hardware frame in parallel with this work.
    AssemblingPayload,
    /// Sending `MultiFramePayload` through channel to downstream consumer.
    SendingDownstream,
}

/// Gatherer-level timestamps populated automatically by state transitions.
///
/// These map directly to `MultiFramePayload`'s gatherer timestamp fields.
#[derive(Debug, Clone, Copy)]
pub struct GathererTimestamps {
    /// Stamped when gatherer is released from the barrier.
    pub post_barrier_ns: i64,
    /// Stamped when the last camera's `FramePacket` is received.
    pub all_frames_received_ns: i64,
    /// Stamped after the `MultiFramePayload` struct is assembled.
    pub payload_assembled_ns: i64,
    /// Stamped just before `multi_frame_sender.send()`.
    pub pre_send_downstream_ns: i64,
}

impl GathererTimestamps {
    pub fn new() -> Self {
        Self {
            post_barrier_ns: 0,
            all_frames_received_ns: 0,
            payload_assembled_ns: 0,
            pre_send_downstream_ns: 0,
        }
    }
}

impl Default for GathererTimestamps {
    fn default() -> Self {
        Self::new()
    }
}

/// Manages the gatherer's runtime state cycle with automatic timestamp recording.
///
/// Every call to `transition_to()`:
/// 1. Validates that the transition is legal.
/// 2. Records a nanosecond timestamp in `timestamps`.
/// 3. Updates the current state.
pub struct GathererStateMachine {
    state: GathererState,
    pub timestamps: GathererTimestamps,
}

impl GathererStateMachine {
    pub fn new() -> Self {
        Self {
            // Start in CollectingFrames — the gatherer collects first,
            // hits the barrier the moment all frames arrive (releasing
            // cameras for their next cycle), THEN assembles and sends the
            // payload while cameras spin for their next frame.
            state: GathererState::CollectingFrames,
            timestamps: GathererTimestamps::new(),
        }
    }

    /// Transition to `next` state.
    ///
    /// Returns `Err(GathererInvalidTransition)` if the transition is not legal.
    /// On success, the corresponding timestamp field(s) are populated
    /// automatically.
    pub fn transition_to(
        &mut self,
        next: GathererState,
    ) -> Result<(), GathererInvalidTransition> {
        let now = performance_counter_nanoseconds();
        self.validate(next)?;
        self.record_timestamp(next, now);
        self.state = next;
        Ok(())
    }

    pub fn current_state(&self) -> GathererState {
        self.state
    }

    fn validate(&self, next: GathererState) -> Result<(), GathererInvalidTransition> {
        let valid = matches!(
            (self.state, next),
            (GathererState::CollectingFrames, GathererState::AllFramesReceived)
                | (GathererState::AllFramesReceived, GathererState::WaitingAtBarrier)
                | (GathererState::WaitingAtBarrier, GathererState::AssemblingPayload)
                | (GathererState::AssemblingPayload, GathererState::SendingDownstream)
                | (GathererState::SendingDownstream, GathererState::CollectingFrames)
        );
        if valid {
            Ok(())
        } else {
            Err(GathererInvalidTransition {
                from: self.state,
                to: next,
            })
        }
    }

    fn record_timestamp(&mut self, next: GathererState, now: i64) {
        match next {
            GathererState::AllFramesReceived => {
                self.timestamps.all_frames_received_ns = now;
            }
            GathererState::WaitingAtBarrier => {
                // No timestamp — about to call barrier.wait(). Capture
                // happens on transition OUT (into AssemblingPayload).
            }
            GathererState::AssemblingPayload => {
                // Barrier just released. Cameras are now spinning for
                // their next frame in parallel with the payload work
                // that happens during AssemblingPayload + SendingDownstream.
                self.timestamps.post_barrier_ns = now;
            }
            GathererState::SendingDownstream => {
                self.timestamps.payload_assembled_ns = now;
                self.timestamps.pre_send_downstream_ns = now;
            }
            GathererState::CollectingFrames => {
                // No timestamp — back to recv'ing the next set of frames.
                // post_send_downstream cannot be captured: the
                // MultiFramePayload was moved into send() before this
                // transition fires.
            }
        }
    }
}

impl Default for GathererStateMachine {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Debug for GathererStateMachine {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("GathererStateMachine")
            .field("state", &self.state)
            .field("timestamps", &self.timestamps)
            .finish()
    }
}

/// Error returned when an invalid gatherer state transition is attempted.
#[derive(Debug, Clone, Copy)]
pub struct GathererInvalidTransition {
    pub from: GathererState,
    pub to: GathererState,
}

impl std::fmt::Display for GathererInvalidTransition {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "Invalid gatherer state transition: {:?} → {:?}",
            self.from, self.to
        )
    }
}

impl std::error::Error for GathererInvalidTransition {}

// ── CameraGroup<Empty> ──────────────────────────────────────────────────────

impl CameraGroup<Empty> {
    /// Create a new empty camera group.
    pub fn new() -> Self {
        let group_id = uuid::Uuid::new_v4().as_simple().to_string()[..6].to_string();
        Self {
            group_id,
            state: Empty,
        }
    }

    /// Load camera configs. Transitions to `Configured`.
    pub fn configure(self, configs: Vec<CameraGroupConfig>) -> CameraGroup<Configured> {
        CameraGroup {
            group_id: self.group_id,
            state: Configured { configs },
        }
    }
}

impl Default for CameraGroup<Empty> {
    fn default() -> Self {
        Self::new()
    }
}

// ── CameraGroup<Configured> ─────────────────────────────────────────────────

impl CameraGroup<Configured> {
    /// Start all cameras and the gatherer.
    ///
    /// This is the big transition: each `Camera<Configured>` in the config
    /// list is started, creating `Camera<Streaming>` instances. Then the
    /// gatherer thread is spawned. On success, returns a `CameraGroup<Streaming>`
    /// with all cameras provably running.
    pub fn start(self) -> anyhow::Result<CameraGroup<Streaming>> {
        let camera_count = self.state.configs.len();
        if camera_count == 0 {
            anyhow::bail!("CameraGroup requires at least one camera config");
        }

        eprintln!("[CameraGroup] starting {camera_count} camera(s) in lockstep");

        let barrier = Arc::new(BreakableBarrier::new(camera_count + 1));

        // Start each camera
        let mut camera_handles = Vec::with_capacity(camera_count);
        let mut camera_thread_handles = Vec::with_capacity(camera_count);
        let mut frame_receivers = Vec::with_capacity(camera_count);
        let mut event_receivers = Vec::with_capacity(camera_count);

        for config in self.state.configs {
            // Build a Camera<Configured> and start it
            let camera_configured = Camera::<CameraConfiguring> {
                transition_log: Vec::new(),
                state: CameraConfiguring {
                    identity: config.identity,
                    config: config.capture_config,
                },
            };

            let camera_streaming = camera_configured
                .start(barrier.clone())
                .map_err(|faulted| {
                    anyhow::anyhow!(
                        "Failed to start camera (source={}): {}",
                        faulted.state.source_state,
                        faulted.error(),
                    )
                })?;

            // Destructure Camera<Streaming> into its components.
            // The receivers go to the gatherer; the command_sender,
            // identity, and config go into a CameraHandle; the thread
            // handle is stored for joining on shutdown.
            let Camera {
                transition_log: _,
                state:
                    CameraStreaming {
                        identity,
                        config: capture_config,
                        frame_receiver,
                        event_receiver,
                        command_sender,
                        thread_handle,
                    },
            } = camera_streaming;

            camera_handles.push(crate::camera::CameraHandle {
                command_sender: command_sender.clone(),
                identity: identity.clone(),
                config: capture_config.clone(),
            });
            camera_thread_handles.push(thread_handle);
            frame_receivers.push(frame_receiver);
            event_receivers.push(event_receiver);
        }

        let (multi_frame_sender, multi_frame_receiver) = mpsc::sync_channel(1);

        let gatherer_handle = super::gatherer::spawn_gatherer(
            frame_receivers,
            event_receivers,
            camera_handles.clone(),
            multi_frame_sender,
            barrier.clone(),
        );

        Ok(CameraGroup {
            group_id: self.group_id,
            state: Streaming {
                camera_handles,
                camera_thread_handles,
                gatherer_handle,
                multi_frame_receiver,
                barrier,
                capture_state: CaptureState::Active,
                recording_state: RecordingState::NotRecording,
            },
        })
    }

    /// Clear configs without starting.
    pub fn clear(self) -> CameraGroup<Empty> {
        CameraGroup {
            group_id: self.group_id,
            state: Empty,
        }
    }
}

// ── CameraGroup<Streaming> ──────────────────────────────────────────────────

impl CameraGroup<Streaming> {
    /// Pause capture. The gatherer stops releasing the barrier; all cameras
    /// block at `barrier.wait()` in their `AtBarrier` substate.
    pub fn pause(&mut self) {
        self.state.capture_state = CaptureState::Paused;
    }

    /// Resume capture. The gatherer will release the barrier on the next
    /// cycle, releasing all cameras simultaneously.
    pub fn resume(&mut self) {
        self.state.capture_state = CaptureState::Active;
    }

    /// Start recording. On the next gatherer cycle, frames will be written
    /// to disk in addition to being forwarded downstream.
    pub fn start_recording(&mut self) {
        self.state.recording_state = RecordingState::Recording;
    }

    /// Stop recording. The recording sink will be finalized and closed.
    pub fn stop_recording(&mut self) {
        self.state.recording_state = RecordingState::NotRecording;
    }

    /// Whether the group is currently paused.
    pub fn is_paused(&self) -> bool {
        self.state.capture_state == CaptureState::Paused
    }

    /// Whether the group is currently recording.
    pub fn is_recording(&self) -> bool {
        self.state.recording_state == RecordingState::Recording
    }

    /// Initiate graceful shutdown of all cameras and the gatherer.
    pub fn shutdown(self) -> CameraGroup<ShuttingDown> {
        tracing::info!("CameraGroup {}: shutting down", self.group_id);
        for handle in &self.state.camera_handles {
            handle.send_shutdown();
        }
        self.state.barrier.break_barrier();

        CameraGroup {
            group_id: self.group_id,
            state: ShuttingDown {
                camera_thread_handles: self.state.camera_thread_handles,
                gatherer_handle: self.state.gatherer_handle,
            },
        }
    }

    /// Receive the next multiframe (blocking with timeout).
    pub fn recv_multiframe(
        &self,
        timeout: std::time::Duration,
    ) -> Result<MultiFramePayload, mpsc::RecvTimeoutError> {
        self.state.multi_frame_receiver.recv_timeout(timeout)
    }

    /// Number of cameras in the group.
    pub fn camera_count(&self) -> usize {
        self.state.camera_handles.len()
    }

    /// Iterate over camera identities for status display.
    pub fn camera_identities(&self) -> Vec<&crate::camera::CameraIdentity> {
        self.state.camera_handles.iter().map(|h| &h.identity).collect()
    }
}

// ── CameraGroup<ShuttingDown> ───────────────────────────────────────────────

impl CameraGroup<ShuttingDown> {
    /// Wait for all camera threads and the gatherer thread to finish.
    ///
    /// Consumes the `ShuttingDown` state and returns `Stopped`.
    pub fn wait(self) -> CameraGroup<Stopped> {
        for handle in self.state.camera_thread_handles {
            if let Err(e) = handle.join() {
                tracing::error!(
                    "CameraGroup {}: camera thread panicked: {}",
                    self.group_id,
                    e.downcast_ref::<&str>()
                        .unwrap_or(&"unknown panic message")
                );
            }
        }
        if let Err(e) = self.state.gatherer_handle.join() {
            tracing::error!(
                "CameraGroup {}: gatherer thread panicked: {}",
                self.group_id,
                e.downcast_ref::<&str>()
                    .unwrap_or(&"unknown panic message")
            );
        }

        CameraGroup {
            group_id: self.group_id,
            state: Stopped,
        }
    }
}

// ── StateDiagram trait ─────────────────────────────────────────────────────

use crate::camera::StateDiagram;

impl StateDiagram for CameraGroup<Empty> {
    fn mermaid_state_diagram() -> &'static str {
        concat!(
            "stateDiagram-v2\n",
            "    [*] --> Empty\n",
            "\n",
            "    Empty --> Configured : configure(configs)\n",
            "    Configured --> Streaming : start()\n",
            "    Configured --> Empty : clear()\n",
            "\n",
            "    Streaming --> ShuttingDown : shutdown()\n",
            "    Streaming --> ShuttingDown : camera faulted\n",
            "\n",
            "    ShuttingDown --> Stopped : wait()\n",
            "    Stopped --> [*]\n",
            "\n",
            "    state Streaming {\n",
            "        state capture_region {\n",
            "            [*] --> Active\n",
            "            Active --> Paused : pause()\n",
            "            Paused --> Active : resume()\n",
            "        }\n",
            "        --\n",
            "        state recording_region {\n",
            "            [*] --> NotRecording\n",
            "            NotRecording --> Recording : start_recording()\n",
            "            Recording --> NotRecording : stop_recording()\n",
            "        }\n",
            "        --\n",
            "        state gatherer_state {\n",
            "            [*] --> CollectingFrames\n",
            "            CollectingFrames --> AllFramesReceived : last camera recv() returned → stamps all_frames_received_ns\n",
            "            AllFramesReceived --> WaitingAtBarrier : enter barrier\n",
            "            WaitingAtBarrier --> AssemblingPayload : barrier released, cameras spinning for next frame → stamps post_barrier_ns\n",
            "            AssemblingPayload --> SendingDownstream : payload built → stamps payload_assembled_ns, pre_send_downstream_ns\n",
            "            SendingDownstream --> CollectingFrames : send() ok\n",
            "        }\n",
            "    }\n",
        )
    }
}

// ── MultiFramePayload re-export ─────────────────────────────────────────────
// (Defined in camera::types but used extensively by the CameraGroup)

pub use crate::camera::MultiFramePayload;

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gatherer_state_machine_full_cycle() {
        let mut gsm = GathererStateMachine::new();
        // Starts in CollectingFrames — gatherer collects first, then hits
        // the barrier (releasing cameras), then assembles + sends in parallel
        // with the cameras spinning for their next frame.
        assert_eq!(gsm.current_state(), GathererState::CollectingFrames);

        gsm.transition_to(GathererState::AllFramesReceived).unwrap();
        assert_eq!(gsm.current_state(), GathererState::AllFramesReceived);
        assert!(gsm.timestamps.all_frames_received_ns > 0);

        gsm.transition_to(GathererState::WaitingAtBarrier).unwrap();
        assert_eq!(gsm.current_state(), GathererState::WaitingAtBarrier);

        gsm.transition_to(GathererState::AssemblingPayload).unwrap();
        assert_eq!(gsm.current_state(), GathererState::AssemblingPayload);
        assert!(gsm.timestamps.post_barrier_ns > 0);

        gsm.transition_to(GathererState::SendingDownstream).unwrap();
        assert_eq!(gsm.current_state(), GathererState::SendingDownstream);
        assert!(gsm.timestamps.payload_assembled_ns > 0);
        assert!(gsm.timestamps.pre_send_downstream_ns > 0);

        gsm.transition_to(GathererState::CollectingFrames).unwrap();
        assert_eq!(gsm.current_state(), GathererState::CollectingFrames);
    }

    #[test]
    fn gatherer_state_machine_rejects_invalid_transitions() {
        let mut gsm = GathererStateMachine::new();

        // Cannot skip from CollectingFrames to WaitingAtBarrier
        assert!(gsm
            .transition_to(GathererState::WaitingAtBarrier)
            .is_err());

        // Advance one step, cannot go backwards
        gsm.transition_to(GathererState::AllFramesReceived).unwrap();
        assert!(gsm
            .transition_to(GathererState::CollectingFrames)
            .is_err());
    }

    #[test]
    fn gatherer_state_machine_timestamps_are_monotonic() {
        let mut gsm = GathererStateMachine::new();
        // Starts in CollectingFrames

        gsm.transition_to(GathererState::AllFramesReceived).unwrap();
        let all_recv = gsm.timestamps.all_frames_received_ns;

        gsm.transition_to(GathererState::WaitingAtBarrier).unwrap();

        gsm.transition_to(GathererState::AssemblingPayload).unwrap();
        let post_barrier = gsm.timestamps.post_barrier_ns;
        assert!(post_barrier >= all_recv, "post_barrier_ns must be >= all_frames_received_ns");

        gsm.transition_to(GathererState::SendingDownstream).unwrap();
        let assembled = gsm.timestamps.payload_assembled_ns;
        assert!(assembled >= post_barrier, "payload_assembled_ns must be >= post_barrier_ns");
    }

    #[test]
    fn camera_group_empty_to_configured() {
        let group = CameraGroup::<Empty>::new();
        assert!(!group.group_id.is_empty());

        let group = group.configure(Vec::new());
        assert!(group.state.configs.is_empty());
    }

    #[test]
    fn camera_group_configured_clear() {
        let group = CameraGroup::<Empty>::new();
        let group = group.configure(Vec::new());
        let _group = group.clear(); // Back to Empty
    }

    #[test]
    fn state_diagram_contains_all_states() {
        let diagram = CameraGroup::<Empty>::mermaid_state_diagram();
        for state in &[
            "Empty",
            "Configured",
            "Streaming",
            "ShuttingDown",
            "Stopped",
            "Active",
            "Paused",
            "NotRecording",
            "Recording",
            "CollectingFrames",
            "AllFramesReceived",
            "WaitingAtBarrier",
            "AssemblingPayload",
            "SendingDownstream",
        ] {
            assert!(
                diagram.contains(state),
                "StateDiagram missing state: {state}"
            );
        }
    }
}
