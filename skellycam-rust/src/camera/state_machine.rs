//! Camera state machine — compile-time-enforced lifecycle states for a single
//! DirectShow camera wrapped by openpnp-capture.
//!
//! ## Design
//! (NOTE - based on: https://hoverbear.org/blog/rust-state-machine-pattern/)
//! Top-level states use the Hoverbear Approach 3 pattern: `Camera<S>` is generic
//! over the state type `S`. Each state is a distinct Rust type, so calling
//! `.shutdown()` on a `Camera<Disconnected>` is a **compile error**, not a
//! runtime panic.
//!
//! Frame-level substates within `Streaming` (WaitingForFrame → FrameAvailable →
//! Capturing → Sending → AtBarrier) are tracked at runtime via `FrameStateMachine`
//! because they cycle 30+ times per second. Capture happens BEFORE the barrier;
//! the barrier is the cycle-completion signal. Every substate transition
//! automatically records a nanosecond-precision monotonic timestamp — the
//! state machine IS the timestamp system.
//!
//! ## State diagram
//!
//! See `docs/state_machines/camera_state_machine.md` for the Mermaid diagram.

use std::sync::mpsc;
use std::sync::Arc;
use std::thread::JoinHandle;

use crate::camera_group::sync_utils::BreakableBarrier;
use crate::timestamps::performance::performance_counter_nanoseconds;

use super::types::{
    CameraConfig, CameraCommand, CameraEvent, CameraIdentity, FrameLifecycleTimestamps,
    FramePacket,
};

// ── Lifecycle audit trail ───────────────────────────────────────────────────

/// A single entry in the camera's lifecycle transition log.
///
/// Each time the camera moves between top-level states (e.g. Disconnected →
/// Enumerated), a `LifecycleTransition` is pushed. This gives a full audit
/// trail of the camera's lifetime — useful for debugging setup failures and
/// profiling setup duration.
#[derive(Debug, Clone)]
pub struct LifecycleTransition {
    pub from_state: &'static str,
    pub to_state: &'static str,
    pub timestamp_ns: i64,
}

// ── State marker types ──────────────────────────────────────────────────────
// Each state carries ONLY the data that is valid in that state.
// No Options. No "this field is meaningless in this state."

/// Camera is not connected. No COM context, no stream, no resources.
#[derive(Debug)]
pub struct Disconnected;

/// Camera identity is known (formats, device path, unique ID from openpnp-capture).
#[derive(Debug)]
pub struct Enumerated {
    pub identity: CameraIdentity,
}

/// Actively configuring the camera: creating COM context, finding format,
/// opening stream, setting exposure, running stabilization.
///
/// This state does the WORK — it can be entered from `Enumerated` (first
/// connection), `Streaming` (settings change), or `Faulted` (retry). On
/// success it goes to `Streaming`. On failure it goes to `Faulted`.
#[derive(Debug)]
pub struct Configuring {
    pub identity: CameraIdentity,
    pub config: CameraConfig,
}

/// Stream open, capture thread running, frames flowing.
///
/// The `FrameStateMachine` lives inside the capture thread (it is not `Sync`).
/// Timestamps are carried out via each `FramePacket.timestamps` and read by
/// the gatherer for statistics.
#[derive(Debug)]
pub struct Streaming {
    pub identity: CameraIdentity,
    pub config: CameraConfig,
    pub frame_receiver: mpsc::Receiver<FramePacket>,
    pub event_receiver: mpsc::Receiver<CameraEvent>,
    pub command_sender: mpsc::Sender<CameraCommand>,
    pub thread_handle: JoinHandle<()>,
}

/// Shutdown signal sent. The capture thread is unwinding; we hold the join
/// handle so we can wait for it.
#[derive(Debug)]
pub struct ShuttingDown {
    pub thread_handle: JoinHandle<()>,
}

/// An error occurred. Carries the error message and the state we faulted FROM
/// so recovery logic knows what resources need to be re-allocated.
///
/// The transition log is carried by the outer `Camera<Faulted>` struct —
/// it is not duplicated here.
#[derive(Debug)]
pub struct Faulted {
    pub error: String,
    pub source_state: &'static str,
}

// ── The machine ─────────────────────────────────────────────────────────────

/// A single camera whose current lifecycle state is encoded in the type
/// parameter `S`.
///
/// # Type-state enforcement
///
/// Methods that transition between states consume `self` and return a new
/// `Camera` with a different `S`. This means the old state is **gone** — you
/// cannot accidentally use a camera in the wrong state because the compiler
/// will not let you.
///
/// ```compile_fail
/// # use skellycam::camera::state_machine::*;
/// let cam = Camera::<Disconnected>::new();
/// cam.shutdown(); // COMPILE ERROR: method not found for `Camera<Disconnected>`
/// ```
#[derive(Debug)]
pub struct Camera<S> {
    pub state: S,
    pub transition_log: Vec<LifecycleTransition>,
}

// ── Frame-level runtime substate ────────────────────────────────────────────

/// High-frequency frame-level states within `Camera<Streaming>`.
///
/// These are NOT type-level states — they cycle 30+ times per second and
/// constructing/destructing type states at that rate would be wasteful.
/// Instead they are tracked at runtime by `FrameStateMachine` with automatic
/// timestamp recording at each transition.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameState {
    /// Spinning on `Cap_hasNewFrame()`, waiting for the next hardware frame.
    WaitingForFrame,
    /// `Cap_captureFrameRaw()` has just returned. The next step is to send
    /// the frame to the gatherer.
    Capturing,
    /// Sending the `FramePacket` through the channel to the gatherer.
    Sending,
    /// Blocked at `BreakableBarrier::wait()`, synchronized with other cameras
    /// and the gatherer.
    AtBarrier,
}

/// Error returned when an invalid frame-level state transition is attempted.
#[derive(Debug, Clone, Copy)]
pub struct InvalidTransition {
    pub from: FrameState,
    pub to: FrameState,
}

impl std::fmt::Display for InvalidTransition {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "Invalid frame state transition: {:?} → {:?}",
            self.from, self.to
        )
    }
}

impl std::error::Error for InvalidTransition {}

/// Manages frame-level runtime substates within the `Streaming` phase.
///
/// Every call to `transition_to()`:
/// 1. Validates that the transition is legal for the current state.
/// 2. Records a nanosecond-precision monotonic timestamp for the transition.
/// 3. Updates the current state.
///
/// The `timestamps` field is populated automatically — no manual
/// `performance_counter_nanoseconds()` calls are needed in the capture loop.
pub struct FrameStateMachine {
    state: FrameState,
    pub timestamps: FrameLifecycleTimestamps,
    frame_number: i64,
}

impl FrameStateMachine {
    /// Create a new frame state machine in the `WaitingForFrame` state.
    ///
    /// `loop_start_ns` is stamped on construction because the first frame's
    /// loop begins when the capture thread enters its main loop.
    pub fn new(frame_number: i64) -> Self {
        let loop_start_ns = performance_counter_nanoseconds();
        Self {
            state: FrameState::WaitingForFrame,
            timestamps: FrameLifecycleTimestamps {
                loop_start_ns,
                frame_available_ns: 0,
                post_barrier_to_capture_ns: 0,
                pre_barrier_ns: 0,
                post_barrier_ns: 0,
                post_capture_ns: 0,
                pre_send_ns: 0,
                post_send_ns: 0,
                gatherer_received_ns: 0,
            },
            frame_number,
        }
    }

    /// Transition to `next` state, stamping the current time.
    ///
    /// Returns `Err(InvalidTransition)` if the transition is not legal from
    /// the current state. On success, the corresponding timestamp field(s)
    /// in `self.timestamps` are populated automatically.
    pub fn transition_to(&mut self, next: FrameState) -> Result<(), InvalidTransition> {
        let now = performance_counter_nanoseconds();
        self.validate(next)?;
        self.record_timestamp(next, now);
        self.state = next;
        Ok(())
    }

    /// Transition to `Capturing` using an externally-recorded timestamp.
    ///
    /// The caller must stamp `frame_available_ns` at the exact moment
    /// `Cap_hasNewFrame()` returns true — before calling `Cap_captureFrameRaw()`.
    /// Passing it here ensures `frame_available_ns` and `post_barrier_to_capture_ns`
    /// reflect the hardware-ready instant, not the post-copy instant.
    pub fn begin_capture(&mut self, frame_available_ns: i64) -> Result<(), InvalidTransition> {
        self.validate(FrameState::Capturing)?;
        self.timestamps.frame_available_ns = frame_available_ns;
        self.timestamps.post_barrier_to_capture_ns = frame_available_ns;
        self.state = FrameState::Capturing;
        Ok(())
    }

    /// The current frame-level state.
    pub fn current_state(&self) -> FrameState {
        self.state
    }

    /// The current frame number.
    pub fn frame_number(&self) -> i64 {
        self.frame_number
    }

    /// Increment the frame number (called at the end of each capture iteration).
    pub fn increment_frame(&mut self) {
        self.frame_number += 1;
    }

    // ── Private helpers ──

    fn validate(&self, next: FrameState) -> Result<(), InvalidTransition> {
        let valid = matches!(
            (self.state, next),
            (FrameState::WaitingForFrame, FrameState::Capturing)
                | (FrameState::Capturing, FrameState::Sending)
                | (FrameState::Sending, FrameState::AtBarrier)
                | (FrameState::AtBarrier, FrameState::WaitingForFrame)
        );
        if valid {
            Ok(())
        } else {
            Err(InvalidTransition {
                from: self.state,
                to: next,
            })
        }
    }

    fn record_timestamp(&mut self, next: FrameState, now: i64) {
        match next {
            FrameState::Capturing => {
                // Fallback: use the current timestamp. In production code,
                // begin_capture(frame_available_ns) is called instead, which
                // passes the hardware-ready timestamp captured before captureFrameRaw().
                // This arm is reached only in tests that call transition_to() directly.
                self.timestamps.frame_available_ns = now;
                self.timestamps.post_barrier_to_capture_ns = now;
            }
            FrameState::Sending => {
                self.timestamps.post_capture_ns = now;
                self.timestamps.pre_send_ns = now;
            }
            FrameState::AtBarrier => {
                self.timestamps.post_send_ns = now;
                self.timestamps.pre_barrier_ns = now;
            }
            FrameState::WaitingForFrame => {
                self.timestamps.post_barrier_ns = now;
                // loop_start_ns is stamped here for the NEXT iteration.
                // Frame 0's loop_start_ns was set by the constructor.
                self.timestamps.loop_start_ns = now;
            }
        }
    }
}

// ── Camera<Disconnected> ────────────────────────────────────────────────────

impl Camera<Disconnected> {
    /// Create a new camera in the Disconnected state.
    ///
    /// This is the entry point. The camera knows nothing about the hardware
    /// at this point — it has not touched openpnp-capture.
    pub fn new() -> Self {
        Self {
            state: Disconnected,
            transition_log: Vec::new(),
        }
    }

    /// Enumerate the camera hardware.
    ///
    /// On success, transitions to `Enumerated` with the camera's identity.
    /// On failure, transitions to `Faulted` with the error.
    pub fn enumerate(
        mut self,
        identity: CameraIdentity,
    ) -> Result<Camera<Enumerated>, Camera<Faulted>> {
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Disconnected",
            to_state: "Enumerated",
            timestamp_ns,
        });
        Ok(Camera {
            transition_log: self.transition_log,
            state: Enumerated { identity },
        })
    }

    /// Enumerate failed — transition directly to Faulted.
    pub fn enumerate_failed(mut self, error: String) -> Camera<Faulted> {
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Disconnected",
            to_state: "Faulted",
            timestamp_ns,
        });
        Camera {
            transition_log: self.transition_log,
            state: Faulted {
                error,
                source_state: "Disconnected",
            },
        }
    }
}

impl Default for Camera<Disconnected> {
    fn default() -> Self {
        Self::new()
    }
}

// ── Camera<Enumerated> ──────────────────────────────────────────────────────

impl Camera<Enumerated> {
    /// Apply a capture configuration and begin hardware setup.
    ///
    /// Transitions to `Configuring`, which does the active work of opening
    /// the stream, setting exposure, and running stabilization.
    pub fn configure(mut self, config: CameraConfig) -> Camera<Configuring> {
        let identity = self.state.identity;
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Enumerated",
            to_state: "Configuring",
            timestamp_ns,
        });
        Camera {
            transition_log: self.transition_log,
            state: Configuring { identity, config },
        }
    }

    /// Release the camera identity without connecting.
    pub fn forget(mut self) -> Camera<Disconnected> {
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Enumerated",
            to_state: "Disconnected",
            timestamp_ns,
        });
        Camera {
            transition_log: self.transition_log,
            state: Disconnected,
        }
    }
}

// ── Camera<Configuring> ─────────────────────────────────────────────────────

impl Camera<Configuring> {
    /// Start streaming: open the hardware stream, configure exposure, run
    /// stabilization, and spawn the capture loop thread.
    ///
    /// This is the big transition — used for both first connection and
    /// mid-stream reconfiguration. On success, returns `Camera<Streaming>`.
    /// On failure, returns `Camera<Faulted>`.
    pub fn start(
        mut self,
        barrier: Arc<BreakableBarrier>,
    ) -> Result<Camera<Streaming>, Camera<Faulted>> {
        match super::thread::spawn_camera_thread(
            &self.state.identity,
            &self.state.config,
            barrier,
        ) {
            Ok((handle, event_receiver, frame_receiver, thread_handle)) => {
                let command_sender = handle.command_sender;
                let timestamp_ns = performance_counter_nanoseconds();
                self.transition_log.push(LifecycleTransition {
                    from_state: "Configuring",
                    to_state: "Streaming",
                    timestamp_ns,
                });
                Ok(Camera {
                    transition_log: self.transition_log,
                    state: Streaming {
                        identity: self.state.identity,
                        config: self.state.config,
                        frame_receiver,
                        event_receiver,
                        command_sender,
                        thread_handle,
                    },
                })
            }
            Err(error) => {
                let timestamp_ns = performance_counter_nanoseconds();
                self.transition_log.push(LifecycleTransition {
                    from_state: "Configuring",
                    to_state: "Faulted",
                    timestamp_ns,
                });
                Err(Camera {
                    transition_log: self.transition_log,
                    state: Faulted {
                        error: format!("{error:#}"),
                        source_state: "Configuring",
                    },
                })
            }
        }
    }
}

// ── Camera<Streaming> ───────────────────────────────────────────────────────

impl Camera<Streaming> {
    /// Initiate graceful shutdown.
    ///
    /// Sends the `Shutdown` command to the capture thread and returns a
    /// `Camera<ShuttingDown>` that owns the thread handle for joining.
    pub fn shutdown(mut self) -> Camera<ShuttingDown> {
        let _ = self.state.command_sender.send(CameraCommand::Shutdown);
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Streaming",
            to_state: "ShuttingDown",
            timestamp_ns,
        });
        Camera {
            transition_log: self.transition_log,
            state: ShuttingDown {
                thread_handle: self.state.thread_handle,
            },
        }
    }

    /// Reconfigure the camera with new settings.
    ///
    /// Transitions to `Configuring` to apply the new config (may involve
    /// closing and reopening the stream if resolution/framerate changed,
    /// or just updating properties on the live stream if only exposure
    /// changed — `Configuring` handles both).
    pub fn reconfigure(mut self, config: CameraConfig) -> Camera<Configuring> {
        let identity = self.state.identity;
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Streaming",
            to_state: "Configuring",
            timestamp_ns,
        });
        Camera {
            transition_log: self.transition_log,
            state: Configuring { identity, config },
        }
    }

    /// Access the frame receiver for non-blocking frame polling.
    pub fn try_recv_frame(&self) -> Result<FramePacket, mpsc::TryRecvError> {
        self.state.frame_receiver.try_recv()
    }

    /// Poll for camera events (errors, etc.).
    pub fn try_recv_event(&self) -> Result<CameraEvent, mpsc::TryRecvError> {
        self.state.event_receiver.try_recv()
    }

    /// The camera's identity.
    pub fn identity(&self) -> &CameraIdentity {
        &self.state.identity
    }

    /// The camera's active configuration.
    pub fn config(&self) -> &CameraConfig {
        &self.state.config
    }

    /// Transition to Faulted due to a runtime capture error.
    pub fn fault(mut self, error: String) -> Camera<Faulted> {
        let timestamp_ns = performance_counter_nanoseconds();
        self.transition_log.push(LifecycleTransition {
            from_state: "Streaming",
            to_state: "Faulted",
            timestamp_ns,
        });
        Camera {
            transition_log: self.transition_log,
            state: Faulted {
                error,
                source_state: "Streaming",
            },
        }
    }
}

// ── Camera<ShuttingDown> ───────────────────────────────────────────────────

impl Camera<ShuttingDown> {
    /// Wait for the capture thread to finish.
    ///
    /// Consumes the `ShuttingDown` state. Returns `Ok(())` if the thread
    /// joined cleanly, or `Err` with the panic message if the thread panicked.
    pub fn wait(self) -> Result<(), String> {
        match self.state.thread_handle.join() {
            Ok(()) => Ok(()),
            Err(e) => Err(format!(
                "Camera thread panicked: {}",
                e.downcast_ref::<&str>()
                    .unwrap_or(&"unknown error")
            )),
        }
    }
}

// ── Camera<Faulted> ────────────────────────────────────────────────────────

impl Camera<Faulted> {
    /// The error message.
    pub fn error(&self) -> &str {
        &self.state.error
    }

    /// Which state we faulted from.
    pub fn source_state(&self) -> &str {
        self.state.source_state
    }

    /// Attempt to recover by restarting from the appropriate state.
    ///
    /// The recovery strategy depends on `source_state`:
    /// - `Configured`: re-attempt `start()` (the setup failed last time)
    /// - `Streaming`: recreate the capture stream from scratch
    pub fn retry(
        self,
        barrier: Arc<BreakableBarrier>,
        identity: CameraIdentity,
        config: CameraConfig,
    ) -> Result<Camera<Streaming>, Camera<Faulted>> {
        match self.state.source_state {
            "Configuring" | "Streaming" | "Enumerated" => {
                let configuring = Camera::<Configuring> {
                    transition_log: self.transition_log,
                    state: Configuring { identity, config },
                };
                configuring.start(barrier)
            }
            _ => Err(self),
        }
    }

    /// Give up on recovery and clean up any remaining resources.
    ///
    /// Currently a no-op (all resources were cleaned up during the fault
    /// transition), but serves as the explicit "I'm done with this camera"
    /// marker.
    pub fn abandon(self) {
        // Resources were released when the fault occurred.
        // The camera is dropped here.
    }
}

// ── StateDiagram trait ─────────────────────────────────────────────────────

/// Types that can produce a Mermaid `stateDiagram-v2` representation.
///
/// The returned string should be a complete Mermaid diagram block that
/// matches the static documentation in `docs/state_machines/`.
pub trait StateDiagram {
    fn mermaid_state_diagram() -> &'static str;
}

impl StateDiagram for Camera<Disconnected> {
    fn mermaid_state_diagram() -> &'static str {
        concat!(
            "stateDiagram-v2\n",
            "    [*] --> Disconnected\n",
            "\n",
            "    Disconnected --> Enumerated : enumerate()\n",
            "    Disconnected --> Faulted : create_context() fails\n",
            "\n",
            "    Enumerated --> Configuring : configure(config)\n",
            "    Enumerated --> Disconnected : forget()\n",
            "\n",
            "    Configuring --> Streaming : start()\n",
            "    Configuring --> Faulted : open_stream() fails\n",
            "\n",
            "    Streaming --> Configuring : reconfigure(new_config)\n",
            "    Streaming --> ShuttingDown : shutdown()\n",
            "    Streaming --> Faulted : capture error\n",
            "\n",
            "    ShuttingDown --> [*] : wait()\n",
            "\n",
            "    Faulted --> Configuring : retry()\n",
            "    Faulted --> [*] : abandon()\n",
            "\n",
            "    state Streaming {\n",
            "        [*] --> WaitingForFrame\n",
            "        WaitingForFrame --> Capturing : hasNewFrame() true → stamps frame_available_ns, post_barrier_to_capture_ns\n",
            "        Capturing --> Sending : captureFrameRaw() + send() → stamps post_capture_ns, pre_send_ns\n",
            "        Sending --> AtBarrier : enter barrier → stamps post_send_ns, pre_barrier_ns\n",
            "        AtBarrier --> WaitingForFrame : barrier released → stamps post_barrier_ns, loop_start_ns\n",
            "        --\n",
            "        WaitingForFrame --> ShuttingDown : shutdown signal\n",
            "        AtBarrier --> ShuttingDown : barrier broken\n",
            "    }\n",
        )
    }
}

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── FrameStateMachine tests ──

    #[test]
    fn frame_state_machine_full_cycle() {
        let mut fsm = FrameStateMachine::new(0);

        // Initial state is WaitingForFrame
        assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
        assert!(fsm.timestamps.loop_start_ns > 0);
        assert_eq!(fsm.timestamps.frame_available_ns, 0);

        // WaitingForFrame → Capturing (hardware reported frame + capture done)
        fsm.transition_to(FrameState::Capturing).unwrap();
        assert_eq!(fsm.current_state(), FrameState::Capturing);
        assert!(fsm.timestamps.frame_available_ns > 0);
        assert!(fsm.timestamps.post_barrier_to_capture_ns > 0);

        // Capturing → Sending (about to send the frame)
        fsm.transition_to(FrameState::Sending).unwrap();
        assert_eq!(fsm.current_state(), FrameState::Sending);
        assert!(fsm.timestamps.post_capture_ns > 0);
        assert!(fsm.timestamps.pre_send_ns > 0);

        // Sending → AtBarrier (frame sent, entering barrier)
        fsm.transition_to(FrameState::AtBarrier).unwrap();
        assert_eq!(fsm.current_state(), FrameState::AtBarrier);
        assert!(fsm.timestamps.post_send_ns > 0);
        assert!(fsm.timestamps.pre_barrier_ns > 0);

        // AtBarrier → WaitingForFrame (barrier released, cycle complete)
        fsm.transition_to(FrameState::WaitingForFrame).unwrap();
        assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
        assert!(fsm.timestamps.post_barrier_ns > 0);
        assert!(fsm.timestamps.loop_start_ns > 0);
    }

    #[test]
    fn frame_state_machine_rejects_invalid_transitions() {
        let mut fsm = FrameStateMachine::new(0);

        // Cannot skip from WaitingForFrame to Sending
        assert!(fsm.transition_to(FrameState::Sending).is_err());

        // Cannot go backwards from Capturing to WaitingForFrame
        fsm.transition_to(FrameState::Capturing).unwrap();
        assert!(fsm.transition_to(FrameState::WaitingForFrame).is_err());

        // Cannot stay in the same state (no self-transitions)
        assert!(fsm.transition_to(FrameState::Capturing).is_err());
    }

    #[test]
    fn frame_state_machine_timestamps_are_monotonic() {
        let mut fsm = FrameStateMachine::new(0);

        fsm.transition_to(FrameState::Capturing).unwrap();
        let fa = fsm.timestamps.frame_available_ns;
        let pbtc = fsm.timestamps.post_barrier_to_capture_ns;
        assert_eq!(fa, pbtc, "frame_available_ns and post_barrier_to_capture_ns stamp on the same transition");

        fsm.transition_to(FrameState::Sending).unwrap();
        let pc = fsm.timestamps.post_capture_ns;
        let ps = fsm.timestamps.pre_send_ns;
        assert!(pc >= fa, "post_capture_ns must be >= frame_available_ns");
        assert_eq!(pc, ps, "post_capture_ns and pre_send_ns stamp on the same transition");

        fsm.transition_to(FrameState::AtBarrier).unwrap();
        let pb = fsm.timestamps.pre_barrier_ns;
        assert!(pb >= ps, "pre_barrier_ns must be >= pre_send_ns");
    }

    // ── Camera lifecycle tests ──

    fn make_test_identity() -> CameraIdentity {
        CameraIdentity {
            camera_name: "Test Camera".into(),
            camera_index: 0,
            camera_id: "abcd".into(),
            device_path: String::new(),
            formats: Vec::new(),
        }
    }

    fn make_test_config() -> CameraConfig {
        CameraConfig {
            camera_id: "abcd".into(),
            camera_index: 0,
            width: 640,
            height: 480,
            exposure: -7,
            exposure_mode: "MANUAL".into(),
            framerate: 30.0,
            rotation: -1,
        }
    }

    #[test]
    fn camera_lifecycle_disconnected_to_configuring() {
        let cam = Camera::<Disconnected>::new();
        assert!(cam.transition_log.is_empty());

        let identity = make_test_identity();
        let cam = cam.enumerate(identity).unwrap();
        assert_eq!(cam.transition_log.len(), 1);
        assert_eq!(cam.transition_log[0].from_state, "Disconnected");
        assert_eq!(cam.transition_log[0].to_state, "Enumerated");

        let config = make_test_config();
        let cam = cam.configure(config);
        assert_eq!(cam.transition_log.len(), 2);
        assert_eq!(cam.transition_log[1].from_state, "Enumerated");
        assert_eq!(cam.transition_log[1].to_state, "Configuring");
        assert_eq!(cam.state.config.width, 640);
        assert_eq!(cam.state.config.height, 480);
    }

    #[test]
    fn camera_enumerated_forget_returns_to_disconnected() {
        let cam = Camera::<Disconnected>::new();
        let identity = make_test_identity();
        let cam = cam.enumerate(identity).unwrap();
        let cam = cam.forget();
        // Should be back in Disconnected, with 2 transition log entries
        assert_eq!(cam.transition_log.len(), 2);
        assert_eq!(
            cam.transition_log.last().unwrap().to_state,
            "Disconnected"
        );
    }

    #[test]
    fn camera_enumerated_forget_returns_to_disconnected_2() {
        let cam = Camera::<Disconnected>::new();
        let identity = make_test_identity();
        let config = make_test_config();
        let cam = cam.enumerate(identity).unwrap();
        let cam = cam.configure(config);
        // Configuring has no forget() — the camera is already setting up.
        // Just verify we reached Configuring.
        assert_eq!(cam.transition_log.len(), 2);
        assert_eq!(cam.transition_log[1].to_state, "Configuring");
    }

    #[test]
    fn camera_disconnected_enumerate_failed() {
        let cam = Camera::<Disconnected>::new();
        let cam = cam.enumerate_failed("no devices found".into());
        assert_eq!(cam.error(), "no devices found");
        assert_eq!(cam.source_state(), "Disconnected");
    }

    #[test]
    fn camera_faulted_abandon() {
        let cam = Camera::<Disconnected>::new();
        let cam = cam.enumerate_failed("test error".into());
        cam.abandon(); // Should not panic
    }

    // ── StateDiagram test ──

    #[test]
    fn state_diagram_contains_all_states() {
        let diagram = Camera::<Disconnected>::mermaid_state_diagram();
        for state in &[
            "Disconnected",
            "Enumerated",
            "Configuring",
            "Streaming",
            "ShuttingDown",
            "Faulted",
            "WaitingForFrame",
            "AtBarrier",
            "Capturing",
            "Sending",
        ] {
            assert!(
                diagram.contains(state),
                "StateDiagram missing state: {state}"
            );
        }
    }
}
