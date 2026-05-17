//! Frame-level runtime state machine for the camera capture hot loop.
//!
//! Cycles at 30+ FPS inside the camera thread. Every transition auto-stamps
//! a nanosecond-precision monotonic timestamp — the state machine IS the
//! timestamp system. No manual `performance_counter_nanoseconds()` calls
//! needed in the capture loop.
//!
//! Legal cycle: WaitingForFrame → Capturing → Sending → AtBarrier → WaitingForFrame

use crate::timestamps::performance::performance_counter_nanoseconds;

use super::types::FrameLifecycleTimestamps;

/// High-frequency frame-level states within the capture loop.
///
/// These are runtime states, not type-level states — they cycle 30+ times
/// per second and constructing/destructing type states at that rate would
/// be wasteful.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameState {
    /// Spinning on `Cap_hasNewFrame()`, waiting for the next hardware frame.
    WaitingForFrame,
    /// `Cap_captureFrameRaw()` has just returned.
    Capturing,
    /// Sending the `FramePacket` through the channel to the gatherer.
    Sending,
    /// Blocked at `BreakableBarrier::wait()`, synchronized with other cameras.
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
            "Invalid frame state transition: {:?} -> {:?}",
            self.from, self.to
        )
    }
}

impl std::error::Error for InvalidTransition {}

/// Manages frame-level runtime substates within the capture loop.
///
/// Every call to `transition_to()`:
/// 1. Validates that the transition is legal for the current state.
/// 2. Records a nanosecond-precision monotonic timestamp.
/// 3. Updates the current state.
///
/// The `timestamps` field is populated automatically.
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
        self.timestamps.post_barrier_to_capture_ns =
            frame_available_ns - self.timestamps.post_barrier_ns;
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
                // Fallback path — production code uses begin_capture() instead.
                self.timestamps.frame_available_ns = now;
                self.timestamps.post_barrier_to_capture_ns =
                    now - self.timestamps.post_barrier_ns;
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
                self.timestamps.loop_start_ns = now;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_cycle() {
        let mut fsm = FrameStateMachine::new(0);

        assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
        assert!(fsm.timestamps.loop_start_ns > 0);
        assert_eq!(fsm.timestamps.frame_available_ns, 0);

        fsm.transition_to(FrameState::Capturing).unwrap();
        assert_eq!(fsm.current_state(), FrameState::Capturing);
        assert!(fsm.timestamps.frame_available_ns > 0);
        assert!(fsm.timestamps.post_barrier_to_capture_ns > 0);

        fsm.transition_to(FrameState::Sending).unwrap();
        assert_eq!(fsm.current_state(), FrameState::Sending);
        assert!(fsm.timestamps.post_capture_ns > 0);
        assert!(fsm.timestamps.pre_send_ns > 0);

        fsm.transition_to(FrameState::AtBarrier).unwrap();
        assert_eq!(fsm.current_state(), FrameState::AtBarrier);
        assert!(fsm.timestamps.post_send_ns > 0);
        assert!(fsm.timestamps.pre_barrier_ns > 0);

        fsm.transition_to(FrameState::WaitingForFrame).unwrap();
        assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
        assert!(fsm.timestamps.post_barrier_ns > 0);
        assert!(fsm.timestamps.loop_start_ns > 0);
    }

    #[test]
    fn rejects_invalid_transitions() {
        let mut fsm = FrameStateMachine::new(0);

        assert!(fsm.transition_to(FrameState::Sending).is_err());

        fsm.transition_to(FrameState::Capturing).unwrap();
        assert!(fsm.transition_to(FrameState::WaitingForFrame).is_err());
        assert!(fsm.transition_to(FrameState::Capturing).is_err());
    }

    #[test]
    fn timestamps_are_monotonic() {
        let mut fsm = FrameStateMachine::new(0);

        fsm.transition_to(FrameState::Capturing).unwrap();
        let fa = fsm.timestamps.frame_available_ns;
        let pbtc = fsm.timestamps.post_barrier_to_capture_ns;
        assert_eq!(fa, pbtc);

        fsm.transition_to(FrameState::Sending).unwrap();
        let pc = fsm.timestamps.post_capture_ns;
        let ps = fsm.timestamps.pre_send_ns;
        assert!(pc >= fa);
        assert_eq!(pc, ps);

        fsm.transition_to(FrameState::AtBarrier).unwrap();
        let pb = fsm.timestamps.pre_barrier_ns;
        assert!(pb >= ps);
    }
}
