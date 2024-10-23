from typing import List

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload


def test_initial_creation(camera_configs_fixture: CameraConfigs) -> None:
    camera_ids: List[CameraId] = list(camera_configs_fixture.keys())
    multi_frame_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_ids)

    assert len(multi_frame_payload.frames) == len(camera_ids)
    assert all(value is None for value in multi_frame_payload.frames.values())
    assert multi_frame_payload.multi_frame_number == 0
    assert isinstance(multi_frame_payload.utc_ns_to_perf_ns.perf_counter_ns, int)
    assert isinstance(multi_frame_payload.utc_ns_to_perf_ns.utc_time_ns, int)


def test_from_previous(multi_frame_payload_fixture: MultiFramePayload) -> None:
    previous_payload: MultiFramePayload = multi_frame_payload_fixture
    next_payload: MultiFramePayload = MultiFramePayload.from_previous(previous_payload)

    assert len(next_payload.frames) == len(previous_payload.frames)
    assert all(value is None for value in next_payload.frames.values())
    assert next_payload.multi_frame_number == previous_payload.multi_frame_number + 1
    assert next_payload.utc_ns_to_perf_ns == previous_payload.utc_ns_to_perf_ns


def test_add_frame(camera_configs_fixture: CameraConfigs,
                   frame_payload_dto_fixture: FramePayload) -> None:
    camera_ids: List[CameraId] = list(camera_configs_fixture.keys())
    multi_frame_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_ids)

    frame_dto: FramePayload = frame_payload_dto_fixture
    frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_ids[0]  # Ensure the camera ID matches
    multi_frame_payload.add_frame(frame_dto)

    assert multi_frame_payload.frames[camera_ids[0]] is not None


def test_full_property(frame_payload_dto_fixture: FramePayload,
                       camera_ids_fixture: List[CameraId]) -> None:
    multi_frame_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_ids_fixture)

    for loop, camera_id in enumerate(camera_ids_fixture):
        assert not multi_frame_payload.full
        frame_dto: FramePayload = frame_payload_dto_fixture
        frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_id
        multi_frame_payload.add_frame(frame_dto)
    assert multi_frame_payload.full
