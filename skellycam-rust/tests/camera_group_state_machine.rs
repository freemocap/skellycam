//! Integration tests for the CameraGroup and GathererStateMachine.

use skellycam::camera_group::{
    CameraGroup, CameraGroupState, GathererInvalidTransition, GathererState,
    GathererStateMachine, GathererTimestamps,
};

// ── GathererStateMachine tests ──────────────────────────────────────────────

#[test]
fn gatherer_full_cycle_and_back() {
    let mut gsm = GathererStateMachine::new();
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

// ── GathererTimestamps default ─────────────────────────────────────────────

#[test]
fn gatherer_timestamps_default_all_zeros() {
    let ts = GathererTimestamps::new();
    assert_eq!(ts.post_barrier_ns, 0);
    assert_eq!(ts.all_frames_received_ns, 0);
    assert_eq!(ts.payload_assembled_ns, 0);
    assert_eq!(ts.pre_send_downstream_ns, 0);
}

// ── CameraGroup lifecycle (no hardware) ────────────────────────────────────

#[test]
fn camera_group_new_requires_configs() {
    let configs = std::collections::HashMap::new();
    let result = std::panic::catch_unwind(|| CameraGroup::new(configs));
    assert!(result.is_err()); // panics on empty configs
}

#[test]
fn camera_group_new_creates_in_created_state() {
    use skellycam::camera::{CameraConfig, CameraIdentity};
    use skellycam::camera_group::CameraGroupConfig;

    let mut configs = std::collections::HashMap::new();
    configs.insert(
        "cam_1".to_string(),
        CameraGroupConfig {
            identity: CameraIdentity {
                camera_name: "Test".into(),
                camera_index: 0,
                camera_id: "cam_1".into(),
                device_path: String::new(),
                formats: Vec::new(),
            },
            capture_config: CameraConfig {
                camera_id: "cam_1".into(),
                camera_index: 0,
                width: 640,
                height: 480,
                exposure: -7,
                exposure_mode: "MANUAL".into(),
                framerate: 30.0,
                rotation: -1,
            },
        },
    );

    let group = CameraGroup::new(configs);
    assert_eq!(group.state(), CameraGroupState::Created);
    assert!(!group.is_paused());
    assert!(!group.is_recording());
    assert_eq!(group.camera_count(), 0); // no cameras until start()
}
