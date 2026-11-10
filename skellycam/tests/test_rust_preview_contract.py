"""The Rust adapter keeps the OpenCV preview and frame contract.

Previews are built natively at the UI's display size, truncated exactly as the Python preview truncates it
(`create_frontend_payload`). Frame orientation: test_rust_camera_group_contract.py.
"""
import multiprocessing
from unittest.mock import Mock

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.rust_camera_group import RustCameraGroup, RustCameraGroupManager
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

DISPLAY = {"A": {"width": 320.9, "height": 180.2}}


def test_display_sizes_reach_the_native_preview_builder_truncated():
    native = Mock()
    native.get_latest_frame_payloads.return_value = {"g": (5, 1.5, b"payload")}
    group = RustCameraGroup("g", {"A": CameraConfig(camera_id="A", camera_index=0)}, native)
    frame_number, timestamp, payload = group.get_latest_frontend_payload(4, DISPLAY)
    assert native.get_latest_frame_payloads.call_args.kwargs == {"if_newer_than": 4, "display_sizes": {"A": (320, 180)}}
    assert (frame_number, timestamp, bytes(payload)) == (5, 1.5, b"payload")


def test_manager_previews_use_display_sizes():
    manager = RustCameraGroupManager(global_kill_flag=multiprocessing.Value("b", False),
                                     worker_registry=Mock(spec=WorkerRegistry))
    manager._native = Mock()
    manager._native.get_latest_frame_payloads.return_value = {"g": (9, 2.0, b"x")}
    manager.camera_groups["g"] = Mock()
    assert set(manager.get_latest_frontend_payloads({"g": 3}, DISPLAY)) == {"g"}
    assert manager._native.get_latest_frame_payloads.call_args.kwargs == {"if_newer_than": 3,
                                                                          "display_sizes": {"A": (320, 180)}}

