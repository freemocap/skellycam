from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import cv2
import numpy as np
from skellycam.core.camera.config.camera_config import CameraConfig

from skellycam.core.camera_group.rust_camera_group import RustCameraGroup, RustCameraGroupManager


def test_unchanged_native_frames_are_rejected_before_jpeg_decode(monkeypatch):
    native = Mock()
    native.get_latest_raw_frames.return_value = {'group': {'camera-A': {'frame_number': 17}}}
    group = RustCameraGroup('group', {}, native)
    decode = Mock(side_effect=AssertionError('Unchanged JPEG must not be decoded'))
    monkeypatch.setattr('cv2.imdecode', decode)
    assert group.get_latest_frames(if_newer_than=17) is None
    decode.assert_not_called()


def test_native_decoding_reuses_caller_owned_frame_storage():
    native = Mock()
    _, jpeg = cv2.imencode('.jpg', np.full((6, 8, 3), 80, dtype=np.uint8))
    source = {'frame_number': 17, 'jpeg_bytes': jpeg.tobytes(), 'timestamps': {
        'loop_start_ns': 10, 'frame_available_ns': 20, 'post_jpeg_extract_ns': 30,
        'pre_send_ns': 40, 'gatherer_received_ns': 50}}
    native.get_latest_raw_frames.return_value = {'group': {'camera-A': source}}
    group = RustCameraGroup('group', {'camera-A': CameraConfig(camera_id='camera-A', camera_index=0)}, native)
    buffers = {}
    first = group.get_latest_frames(frame_buffers=buffers)['camera-A']
    source['frame_number'] = 18
    second = group.get_latest_frames(if_newer_than=17, frame_buffers=buffers)['camera-A']
    assert first is second
    assert int(second.frame_metadata.frame_number[0]) == 18
    assert np.all(second.image == 80)


@pytest.mark.parametrize('rotation', [-1, 0, 1, 2])
def test_native_frames_restore_sensor_orientation_before_python_consumers_rotate(rotation):
    """Native raw JPEGs are display-oriented; Python frame records are sensor-oriented."""
    sensor_image = np.random.default_rng(19).integers(0, 256, (48, 80, 3), dtype=np.uint8)
    display_image = sensor_image if rotation == -1 else cv2.rotate(sensor_image, rotation)
    _, jpeg = cv2.imencode('.jpg', display_image)
    decoded_display = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
    native = Mock()
    native.get_latest_raw_frames.return_value = {'group': {'000a': {
        'frame_number': 17, 'jpeg_bytes': jpeg.tobytes(), 'timestamps': {
            'loop_start_ns': 10, 'frame_available_ns': 20, 'post_jpeg_extract_ns': 30,
            'pre_send_ns': 40, 'gatherer_received_ns': 50}}}}
    config = CameraConfig(camera_id='000a', camera_index=3, rotation=rotation,
                          resolution={'width': 80, 'height': 48})
    group = RustCameraGroup('group', {'000a': config}, native)
    buffers = {}
    frame = group.get_latest_frames(frame_buffers=buffers)['000a']
    assert frame.image[0].shape == sensor_image.shape
    assert int(frame.frame_metadata.camera_info.camera_index[0]) == 3
    applied_rotation = int(frame.frame_metadata.camera_info.rotation[0])
    displayed = frame.image[0] if applied_rotation == -1 else cv2.rotate(frame.image[0], applied_rotation)
    np.testing.assert_array_equal(displayed, decoded_display)
    assert group.get_latest_frames(frame_buffers=buffers)['000a'] is frame


def test_new_group_frames_are_not_hidden_by_an_older_groups_threshold():
    native = Mock()
    frames = {"old": (101, 123.0, b"old"), "new": (1, 124.0, b"new")}
    native.get_latest_frame_payloads.side_effect = lambda if_newer_than: {
        key: value for key, value in frames.items() if value[0] > if_newer_than
    }
    manager = RustCameraGroupManager.__new__(RustCameraGroupManager)
    manager._native = native
    manager.camera_groups = {"old": object(), "new": object()}
    manager.closing = False
    manager._framerate_timestamps = {}
    result = manager.get_latest_frontend_payloads({"old": 101})
    assert set(result) == {"new"}
    assert result["new"][2].readonly
    assert result["new"][2].tobytes() == b"new"


@pytest.mark.asyncio
async def test_close_finalizes_recording_then_releases_only_its_group():
    native = Mock()
    group = RustCameraGroup("selected", {}, native)
    group._recording_info = object()
    async def fail_finalization():
        group._recording_info = None
        raise RuntimeError("disk error")
    group.stop_recording = fail_finalization
    with pytest.raises(RuntimeError, match="disk error"):
        await group.close()
    native.close_group.assert_called_once_with("selected")
    native.close_all_groups.assert_not_called()
    await group.close()
    native.close_group.assert_called_once()


@pytest.mark.asyncio
async def test_closing_empty_manager_does_not_disable_future_polling():
    manager = RustCameraGroupManager.__new__(RustCameraGroupManager)
    manager.camera_groups = {}
    manager._framerate_timestamps = {}
    manager.closing = False
    await manager.close_all_camera_groups()
    assert not manager.closing
