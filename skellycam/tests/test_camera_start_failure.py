"""A failed camera start says what was requested, what happened, why, and what to try."""
import asyncio
from types import SimpleNamespace

import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group import camera_backend_manager as backend
from skellycam.core.camera_group.camera_errors import CameraConnectionCancelled, CameraStartFailed
from skellycam.core.camera_group.camera_start_failure import explain_start_failure

NO_FRAMES = RuntimeError("Failed to start camera group: 1 of 3 requested camera(s) did not start; 9412: Camera "
                         "Global Shutter Camera #4 [id: 9412] thread error: camera stabilization timed out waiting "
                         "for frames")


def configs(*camera_ids, fps=90.0):
    return {camera_id: CameraConfig(camera_id=camera_id, camera_index=index, resolution={"width": 1280, "height": 720},
                                    framerate=fps, capture_fourcc="MJPG")
            for index, camera_id in enumerate(camera_ids)}


def detected(**connections):
    return [SimpleNamespace(camera_id=camera_id, usb_version=version) for camera_id, version in connections.items()]


def test_usb_reset_is_explained_with_connections_and_advice():
    text = explain_start_failure(NO_FRAMES, configs("1b2b", "891e", "a272"),
                                 detected(**{"1b2b": "USB 3", "891e": "USB 2"}), usb_disconnects=11)
    assert "Could not start 3 camera(s) with these settings." in text
    assert "1b2b (USB 3): MJPG 1280×720 at 90 fps" in text and "891e (USB 2)" in text
    assert "a272 (USB connection unknown)" in text
    assert "Windows reported 11 USB device disconnection(s) during the start." in text
    assert "Not detected after the failure: a272." in text
    assert "USB controller reset" in text and "Lower the frame rate or resolution" in text


def test_a_camera_without_frames_is_explained_without_claiming_a_reset():
    text = explain_start_failure(NO_FRAMES, configs("1b2b", "9412", fps=30.0),
                                 detected(**{"1b2b": "USB 3", "9412": "USB 3"}), usb_disconnects=0)
    assert "in use by another program" in text and "Close other programs" in text
    assert "reset" not in text


def test_a_camera_that_cannot_open_is_explained():
    error = RuntimeError("Camera Global Shutter Camera #0 thread error: device usb#x is not connected")
    text = explain_start_failure(error, configs("1b2b"), detected(**{"1b2b": "USB 3"}), usb_disconnects=None)
    assert "could not be opened" in text and "check its cable" in text


def test_ids_that_are_not_detection_ids_do_not_read_as_missing_cameras():
    text = explain_start_failure(NO_FRAMES, configs("cam0", "cam1"), detected(**{"1b2b": "USB 3"}), usb_disconnects=0)
    assert "Not detected after the failure" not in text


def test_default_frame_rate_is_named_as_such():
    text = explain_start_failure(NO_FRAMES, configs("1b2b", fps=-1.0), detected(**{"1b2b": "USB 3"}), 0)
    assert "at the camera's default frame rate" in text


class FailingManager:
    def __init__(self, error):
        self.error = error
        self.camera_groups = {}

    async def create_or_update_camera_group(self, configs):
        raise self.error


def manager_failing_with(error, monkeypatch):
    manager = backend.CameraBackendManager.__new__(backend.CameraBackendManager)
    manager._manager = FailingManager(error)
    manager.backend = "rust"
    manager._configuration_lock = asyncio.Lock()
    manager._recording_requested = False
    monkeypatch.setattr(backend, "describe_start_failure", lambda error, configs, started: f"explained: {error}")
    return manager


def test_backend_manager_explains_start_failures(monkeypatch):
    manager = manager_failing_with(NO_FRAMES, monkeypatch)
    with pytest.raises(CameraStartFailed, match="explained: Failed to start camera group") as failure:
        asyncio.run(manager.create_or_update_camera_group(configs("1b2b"), "rust"))
    assert failure.value.__cause__ is NO_FRAMES


def test_backend_manager_passes_cancellation_through(monkeypatch):
    cancelled = CameraConnectionCancelled("Connection cancelled")
    manager = manager_failing_with(cancelled, monkeypatch)
    with pytest.raises(CameraConnectionCancelled):
        asyncio.run(manager.create_or_update_camera_group(configs("1b2b"), "rust"))
