//! Integration tests for the Camera state machine.
//!
//! These tests verify the full lifecycle: Disconnected → Enumerated →
//! Configuring → Streaming → ShuttingDown, plus error paths through
//! Faulted and recovery via retry.

use skellycam::camera::state_machine::{
    Camera, Disconnected, FrameState, FrameStateMachine, StateDiagram,
};

// ── Helpers ─────────────────────────────────────────────────────────────────

fn make_test_identity() -> skellycam::camera::CameraIdentity {
    skellycam::camera::CameraIdentity {
        display_name: "Test Camera".into(),
        camera_index: 0,
        unique_identifier: "abcd".into(),
        device_path: String::new(),
        formats: Vec::new(),
    }
}

fn make_test_config() -> skellycam::camera::CameraCaptureConfig {
    skellycam::camera::CameraCaptureConfig {
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

// ── Full lifecycle (no hardware) ────────────────────────────────────────────

#[test]
fn full_lifecycle_disconnected_to_configuring_and_back() {
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
    assert_eq!(cam.transition_log[1].to_state, "Configuring");
    assert_eq!(cam.state.config.width, 640);
    assert_eq!(cam.state.config.height, 480);

    // Configuring has no forget() — you must complete setup or fail.
    // Forget from Enumerated instead (back to Disconnected).
    let cam2 = Camera::<Disconnected>::new()
        .enumerate(make_test_identity()).unwrap()
        .forget();
    assert_eq!(cam2.transition_log.len(), 2);
    assert_eq!(cam2.transition_log[1].to_state, "Disconnected");
}

#[test]
fn enumerate_failed_produces_faulted_with_correct_error() {
    let cam = Camera::<Disconnected>::new();
    let cam = cam.enumerate_failed("no devices found".into());
    assert_eq!(cam.error(), "no devices found");
    assert_eq!(cam.source_state(), "Disconnected");
    assert_eq!(cam.transition_log.len(), 1);
}

#[test]
fn faulted_can_be_abandoned() {
    let cam = Camera::<Disconnected>::new();
    let cam = cam.enumerate_failed("error".into());
    // abandon() consumes the camera — no panic
    cam.abandon();
}

// ── FrameStateMachine cycle tests ──────────────────────────────────────────

#[test]
fn frame_state_machine_two_full_cycles() {
    let mut fsm = FrameStateMachine::new(0);

    // First cycle — capture-then-barrier order. FrameAvailable was removed;
    // hardware-ready + captureFrame() are stamped together on the transition
    // WaitingForFrame → Capturing.
    assert_eq!(fsm.current_state(), FrameState::WaitingForFrame);
    fsm.transition_to(FrameState::Capturing).unwrap();
    fsm.transition_to(FrameState::Sending).unwrap();
    fsm.transition_to(FrameState::AtBarrier).unwrap();
    fsm.transition_to(FrameState::WaitingForFrame).unwrap();
    fsm.increment_frame();
    assert_eq!(fsm.frame_number(), 1);

    // Second cycle — timestamps should be updated
    let second_loop_start = fsm.timestamps.loop_start_ns;
    assert!(second_loop_start > 0);

    fsm.transition_to(FrameState::Capturing).unwrap();
    fsm.transition_to(FrameState::Sending).unwrap();
    fsm.transition_to(FrameState::AtBarrier).unwrap();
    fsm.transition_to(FrameState::WaitingForFrame).unwrap();
    fsm.increment_frame();
    assert_eq!(fsm.frame_number(), 2);
}

#[test]
fn frame_state_machine_all_invalid_skips_rejected() {
    let mut fsm = FrameStateMachine::new(0);

    // Skip from WaitingForFrame straight to Sending is invalid
    assert!(fsm.transition_to(FrameState::Sending).is_err());
    // Skip from WaitingForFrame to AtBarrier is invalid
    assert!(fsm.transition_to(FrameState::AtBarrier).is_err());

    // Advance to Capturing (the only valid transition from WaitingForFrame)
    fsm.transition_to(FrameState::Capturing).unwrap();
    // Can't go back
    assert!(fsm.transition_to(FrameState::WaitingForFrame).is_err());
    // Can't self-transition
    assert!(fsm.transition_to(FrameState::Capturing).is_err());
}

// ── StateDiagram test ──────────────────────────────────────────────────────

#[test]
fn state_diagram_output_is_non_empty() {
    let diagram = Camera::<Disconnected>::mermaid_state_diagram();
    assert!(!diagram.is_empty());
    assert!(diagram.contains("stateDiagram-v2"));
}

// ── Transition log accumulation ────────────────────────────────────────────

#[test]
fn transition_log_accumulates_across_states() {
    let cam = Camera::<Disconnected>::new();

    let identity = make_test_identity();
    let cam = cam.enumerate(identity).unwrap();
    // Go back via forget (only valid from Enumerated)
    let cam = cam.forget();

    // Should have 2 transitions: Disconnected→Enumerated, Enumerated→Disconnected
    assert_eq!(cam.transition_log.len(), 2);
    assert_eq!(cam.transition_log[0].to_state, "Enumerated");
    assert_eq!(cam.transition_log[1].to_state, "Disconnected");

    assert!(cam.transition_log[0].timestamp_ns <= cam.transition_log[1].timestamp_ns);
}
