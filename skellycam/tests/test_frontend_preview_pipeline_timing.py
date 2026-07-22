"""Tests for server-side preview pipeline timing buffers (JPEG path + multiframe sync)."""
import uuid

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from skellycam.core.types.frontend_payload_bytearray import (
    PREVIEW_MULTIFRAME_INTER_CAMERA_GRAB_SPREAD_MS,
    PREVIEW_TIMING_JPEG_RESIZE_MS,
    PREVIEW_TIMING_WS_PAYLOAD_PREPARE_MS,
    create_frontend_payload,
    get_and_clear_frontend_preview_multiframe_samples,
    get_and_clear_frontend_preview_timing_samples,
)


def _make_fake_frames(
    camera_ids: list[str],
    frame_number: int = 42,
) -> dict[str, np.recarray]:
    frames: dict[str, np.recarray] = {}
    for i, cam_id in enumerate(camera_ids):
        config = CameraConfig(
            camera_id=cam_id,
            camera_index=i,
            resolution=ImageResolution(height=48, width=64),
        )
        frame_dtype = create_frame_dtype(config)
        frame = np.recarray(1, dtype=frame_dtype)
        frame.frame_metadata.camera_info[0] = config.to_frame_camera_info()
        frame.frame_metadata.frame_number[0] = frame_number
        frame.frame_metadata.timestamps.pre_frame_grab_ns[0] = 1_000_000_000
        frame.frame_metadata.timestamps.post_frame_grab_ns[0] = 1_001_000_000
        frame.image[0] = np.random.randint(0, 255, (48, 64, 3), dtype=np.uint8)
        frames[cam_id] = frame
    return frames


def test_preview_timing_recorded_when_camera_group_id_set() -> None:
    frames = _make_fake_frames(["cam0"], frame_number=2)
    group_id = str(uuid.uuid4())
    create_frontend_payload(latest_frames=frames, camera_group_id=group_id)
    per_cam = get_and_clear_frontend_preview_timing_samples(group_id)
    assert "cam0" in per_cam
    assert PREVIEW_TIMING_JPEG_RESIZE_MS in per_cam["cam0"]
    assert len(per_cam["cam0"][PREVIEW_TIMING_JPEG_RESIZE_MS]) >= 1
    assert get_and_clear_frontend_preview_timing_samples(group_id) == {}


def test_inter_camera_grab_spread_multiframe_sample() -> None:
    frames = _make_fake_frames(["cam0", "cam1"], frame_number=3)
    frames["cam0"].frame_metadata.timestamps.post_frame_grab_ns[0] = 1_000_000_000
    frames["cam1"].frame_metadata.timestamps.post_frame_grab_ns[0] = 1_005_000_000
    group_id = str(uuid.uuid4())
    create_frontend_payload(latest_frames=frames, camera_group_id=group_id)
    multiframe = get_and_clear_frontend_preview_multiframe_samples(group_id)
    assert PREVIEW_MULTIFRAME_INTER_CAMERA_GRAB_SPREAD_MS in multiframe
    assert multiframe[PREVIEW_MULTIFRAME_INTER_CAMERA_GRAB_SPREAD_MS][-1] == pytest.approx(5.0)
    assert get_and_clear_frontend_preview_multiframe_samples(group_id) == {}


def test_ws_payload_prepare_recorded_once_per_multiframe() -> None:
    frames = _make_fake_frames(["cam0", "cam1"], frame_number=4)
    group_id = str(uuid.uuid4())
    create_frontend_payload(latest_frames=frames, camera_group_id=group_id)
    per_cam = get_and_clear_frontend_preview_timing_samples(group_id)
    for stages in per_cam.values():
        assert PREVIEW_TIMING_WS_PAYLOAD_PREPARE_MS not in stages
    multiframe = get_and_clear_frontend_preview_multiframe_samples(group_id)
    assert PREVIEW_TIMING_WS_PAYLOAD_PREPARE_MS in multiframe
    assert len(multiframe[PREVIEW_TIMING_WS_PAYLOAD_PREPARE_MS]) == 1
