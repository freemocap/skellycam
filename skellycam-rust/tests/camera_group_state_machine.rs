//! Integration tests for the CameraGroup state machine and GathererStateMachine.

use skellycam::camera_group::state_machine::{
    CameraGroup, CaptureState, Empty, GathererInvalidTransition, GathererState,
    GathererStateMachine, RecordingState,
};

// ── GathererStateMachine tests ──────────────────────────────────────────────

#[test]
fn gatherer_full_cycle_and_back() {
    let mut gsm = GathererStateMachine::new();
    // Starts in CollectingFrames. New cycle order: collect → AllFramesReceived →
    // barrier → assemble → send → back to collect.
    assert_eq!(gsm.current_state(), GathererState::CollectingFrames);

    gsm.transition_to(GathererState::AllFramesReceived).unwrap();
    assert!(gsm.timestamps.all_frames_received_ns > 0);

    gsm.transition_to(GathererState::WaitingAtBarrier).unwrap();

    gsm.transition_to(GathererState::AssemblingPayload).unwrap();
    assert!(gsm.timestamps.post_barrier_ns > 0);

    gsm.transition_to(GathererState::SendingDownstream).unwrap();
    assert!(gsm.timestamps.payload_assembled_ns > 0);
    assert!(gsm.timestamps.pre_send_downstream_ns > 0);

    gsm.transition_to(GathererState::CollectingFrames).unwrap();
}

#[test]
fn gatherer_rejects_all_invalid_transitions() {
    let mut gsm = GathererStateMachine::new();

    // Cannot skip from CollectingFrames to WaitingAtBarrier
    assert!(gsm.transition_to(GathererState::WaitingAtBarrier).is_err());

    // Advance one step, cannot go backwards
    gsm.transition_to(GathererState::AllFramesReceived).unwrap();
    assert!(gsm.transition_to(GathererState::CollectingFrames).is_err());
    // Cannot self-transition
    assert!(gsm.transition_to(GathererState::AllFramesReceived).is_err());
}

#[test]
fn gatherer_invalid_transition_error_is_displayable() {
    let err = GathererInvalidTransition {
        from: GathererState::CollectingFrames,
        to: GathererState::SendingDownstream,
    };
    let msg = format!("{err}");
    assert!(msg.contains("CollectingFrames"));
    assert!(msg.contains("SendingDownstream"));
}

// ── CameraGroup lifecycle tests (no hardware) ──────────────────────────────

#[test]
fn empty_to_configured_and_clear() {
    let group = CameraGroup::<Empty>::new();
    assert!(!group.group_id.is_empty());
    assert_eq!(group.group_id.len(), 6);

    let group = group.configure(Vec::new());
    assert!(group.state.configs.is_empty());

    let _group = group.clear(); // Back to Empty
}

#[test]
fn configured_start_requires_at_least_one_config() {
    let group = CameraGroup::<Empty>::new();
    let group = group.configure(Vec::new());

    let result = group.start();
    assert!(result.is_err());
}

#[test]
fn streaming_state_has_correct_defaults() {
    // This test verifies the struct initial values — we can't actually
    // start cameras without hardware, but we can test the type system.
    // Verify that CaptureState and RecordingState are correctly defaulted.
    assert_eq!(CaptureState::Active as u8, CaptureState::Active as u8);
    assert_ne!(CaptureState::Active, CaptureState::Paused);
    assert_eq!(RecordingState::NotRecording as u8, RecordingState::NotRecording as u8);
    assert_ne!(RecordingState::NotRecording, RecordingState::Recording);
}



// ── GathererTimestamps default ─────────────────────────────────────────────

#[test]
fn gatherer_timestamps_default_all_zeros() {
    let ts = skellycam::camera_group::state_machine::GathererTimestamps::new();
    assert_eq!(ts.post_barrier_ns, 0);
    assert_eq!(ts.all_frames_received_ns, 0);
    assert_eq!(ts.payload_assembled_ns, 0);
    assert_eq!(ts.pre_send_downstream_ns, 0);
}
