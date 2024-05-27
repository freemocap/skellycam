from skellycam.core.frames.multi_frame_payload import MultiFramePayload


def test_multi_frame_create_empty(camera_ids_fixture):
    # Arrange
    multi_frame_payload = MultiFramePayload.create_empty(camera_ids=camera_ids_fixture, multi_frame_number=0)

    # Assert
    assert multi_frame_payload.multi_frame_number == 0
    assert len(multi_frame_payload.frames) == len(camera_ids_fixture)
    assert all([frame is None for frame in multi_frame_payload.frames.values()])
    assert multi_frame_payload.utc_ns_to_perf_ns["time.time_ns"] > 0
    assert multi_frame_payload.utc_ns_to_perf_ns["time.perf_counter_ns"] > 0
    assert not multi_frame_payload.full
    assert str(multi_frame_payload)


def test_multi_frame_from_previous(multi_frame_payload_fixture):
    # Arrange
    previous_multi_frame_payload = multi_frame_payload_fixture
    multi_frame_payload = MultiFramePayload.from_previous(previous_multi_frame_payload)

    # Assert
    assert multi_frame_payload.multi_frame_number == previous_multi_frame_payload.multi_frame_number + 1
    assert len(multi_frame_payload.frames) == len(previous_multi_frame_payload.frames)
    assert all([frame is None for frame in multi_frame_payload.frames.values()])
    assert multi_frame_payload.utc_ns_to_perf_ns == previous_multi_frame_payload.utc_ns_to_perf_ns
    assert not multi_frame_payload.full
