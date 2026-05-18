//! Frame-level runtime state machine for the camera capture hot loop.
//!
//! Cycles at 30+ FPS inside the camera thread. The FSM enforces the legal
//! state-transition order; the camera thread stamps every timestamp at the
//! precise real-world call site (immediately before / after the underlying
//! work). This decoupling lets timestamps reflect what actually happened
//! rather than what the FSM transition conceptually represents — important
//! for the JPEG-extract timing, which spans the work between two FSM states
//! rather than at the transition itself.
//!
//! Legal cycle: WaitingForFrame → Capturing → Sending → AtBarrier → WaitingForFrame

use crate::timestamps::performance::performance_counter_nanoseconds;

use super::types::FrameLifecycleTimestamps;

/// High-frequency frame-level states within the capture loop.
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
/// `transition_to()` validates the transition and updates state; it does NOT
/// stamp timestamps. The camera thread is responsible for stamping each
/// timestamp at the precise call site where the underlying work occurs.
/// `begin_capture()` is the one exception: it takes `frame_available_ns`
/// externally (stamped by the camera thread immediately after
/// `Cap_hasNewFrame()` returns true) and stores it for inclusion in the
/// outgoing `FramePacket`.
pub struct FrameStateMachine {
    state: FrameState,
    pub timestamps: FrameLifecycleTimestamps,
    frame_number: i64,
}

impl FrameStateMachine {
    /// Create a new frame state machine in the `WaitingForFrame` state.
    ///
    /// `loop_start_ns` is stamped now because the capture loop is about to
    /// begin its first iteration (the camera has finished stabilization and
    /// the FSM is being constructed at the top of the capture loop).
    pub fn new(frame_number: i64) -> Self {
        let loop_start_ns = performance_counter_nanoseconds();
        Self {
            state: FrameState::WaitingForFrame,
            timestamps: FrameLifecycleTimestamps {
                loop_start_ns,
                frame_available_ns: 0,
                post_jpeg_extract_ns: 0,
                pre_send_ns: 0,
                gatherer_received_ns: 0,
            },
            frame_number,
        }
    }

    /// Validate and apply a state transition. Does not stamp any timestamps.
    pub fn transition_to(&mut self, next: FrameState) -> Result<(), InvalidTransition> {
        self.validate(next)?;
        self.state = next;
        Ok(())
    }

    /// Transition to `Capturing`, recording the hardware-ready timestamp.
    ///
    /// The caller stamps `frame_available_ns` at the exact moment
    /// `Cap_hasNewFrame()` returns true — before calling
    /// `Cap_captureFrameRaw()`. Passing it here ensures `frame_available_ns`
    /// reflects the hardware-ready instant rather than the post-capture
    /// instant.
    pub fn begin_capture(&mut self, frame_available_ns: i64) -> Result<(), InvalidTransition> {
        self.validate(FrameState::Capturing)?;
        self.timestamps.frame_available_ns = frame_available_ns;
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
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_cycle() {
        crate::init_logging("error");
        let mut fsm = FrameStateMachine::new(0);

        assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
        assert!(fsm.timestamps.loop_start_ns > 0);
        assert_eq!(fsm.timestamps.frame_available_ns, 0);

        let fa = performance_counter_nanoseconds();
        fsm.begin_capture(fa).unwrap();
        assert_eq!(fsm.current_state(), FrameState::Capturing);
        assert_eq!(fsm.timestamps.frame_available_ns, fa);

        fsm.transition_to(FrameState::Sending).unwrap();
        assert_eq!(fsm.current_state(), FrameState::Sending);

        fsm.transition_to(FrameState::AtBarrier).unwrap();
        assert_eq!(fsm.current_state(), FrameState::AtBarrier);

        fsm.transition_to(FrameState::WaitingForFrame).unwrap();
        assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
    }

    #[test]
    fn rejects_invalid_transitions() {
        crate::init_logging("error");
        let mut fsm = FrameStateMachine::new(0);

        assert!(fsm.transition_to(FrameState::Sending).is_err());

        let fa = performance_counter_nanoseconds();
        fsm.begin_capture(fa).unwrap();
        assert!(fsm.transition_to(FrameState::WaitingForFrame).is_err());
        assert!(fsm.begin_capture(fa).is_err());
    }

    #[test]
    fn timestamps_are_caller_stamped() {
        crate::init_logging("error");
        let mut fsm = FrameStateMachine::new(0);

        // Caller stamps frame_available, post_jpeg_extract, pre_send at the
        // real call sites — not the FSM. Barrier timestamps deliberately
        // omitted from the FrameLifecycleTimestamps struct: they would be
        // stamped after the packet leaves the camera thread, so any value
        // carried in the packet would belong to the PREVIOUS iteration
        // (off-by-one bug). See the note in `camera/types.rs`.
        let fa = performance_counter_nanoseconds();
        fsm.begin_capture(fa).unwrap();
        let pje = performance_counter_nanoseconds();
        fsm.timestamps.post_jpeg_extract_ns = pje;
        assert!(pje >= fa, "post_jpeg_extract must follow frame_available");

        fsm.transition_to(FrameState::Sending).unwrap();
        let ps = performance_counter_nanoseconds();
        fsm.timestamps.pre_send_ns = ps;
        assert!(ps >= pje, "pre_send must follow post_jpeg_extract");

        // AtBarrier and WaitingForFrame transitions are still part of the
        // FSM (the camera thread still calls barrier.wait() between iterations),
        // but no timestamps are stored — those moments happen after the
        // packet has been sent downstream.
        fsm.transition_to(FrameState::AtBarrier).unwrap();
        fsm.transition_to(FrameState::WaitingForFrame).unwrap();

        // loop_start_ns is updated for the next iteration by the camera
        // thread directly. The FSM doesn't auto-update it.
        let next_loop_start = performance_counter_nanoseconds();
        fsm.timestamps.loop_start_ns = next_loop_start;
        assert!(next_loop_start > ps);
    }
}
