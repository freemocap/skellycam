"""Supported capture modes come from native detection, matched by device path."""
import sys
from types import SimpleNamespace
from unittest.mock import patch

import cv2
from cv2_enumerate_cameras.camera_info import CameraInfo

from skellycam.core.device_detection.detect_cameras_devices import detect_available_cameras

CAMERA_NAME = "Global Shutter Camera"
# DirectShow device paths reported by two attached ELP USB cameras.
PATH_A = r"\\?\usb#vid_32e4&pid_5234&mi_00#6&fadbf3b&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
PATH_B = r"\\?\usb#vid_32e4&pid_5234&mi_00#6&243c3b76&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
# Media Foundation names camera A through a different interface class.
MSMF_PATH_A = r"\\?\usb#vid_32e4&pid_5234&mi_00#6&fadbf3b&0&0000#{e5323777-f976-4f5b-9b55-b94699c46e44}\global"


def opencv_camera(index: int, path: str) -> CameraInfo:
    return CameraInfo(index, CAMERA_NAME, path, 0x32E4, 0x5234, cv2.CAP_DSHOW)


def capture_format(width: int, height: int, fps: int, fourcc_str: str = "MJPG") -> dict:
    return {"width": width, "height": height, "fps": fps,
            "fourcc": int.from_bytes(fourcc_str.encode(), "little"), "fourcc_str": fourcc_str}


def native_detection(camera_index: int, path: str, formats: list[dict]) -> dict:
    # openpnp-capture identifies Windows devices as "<friendly name> <DevicePath>".
    return {"camera_index": camera_index, "display_name": CAMERA_NAME, "unique_identifier": "1b2b",
            "device_path": f"{CAMERA_NAME} {path}", "formats": formats, "available": True}


def detect(opencv_cameras: list[CameraInfo], native_module) -> list:
    with patch("skellycam.core.device_detection.detect_cameras_devices.enumerate_cameras",
               return_value=opencv_cameras), patch.dict(sys.modules, {"_skellycam_rust": native_module}):
        return detect_available_cameras()


def native_module_returning(detections: list[dict]):
    return SimpleNamespace(detect_cameras=lambda: detections)


def test_detect_endpoint_matches_modes_by_device_path_not_index(client):
    # Native enumeration order and indices deliberately disagree with OpenCV's.
    native = native_module_returning([
        native_detection(0, PATH_B, [capture_format(640, 480, 30)]),
        native_detection(1, PATH_A, [capture_format(1920, 1200, 120), capture_format(1920, 1200, 60)]),
    ])
    with patch("skellycam.core.device_detection.detect_cameras_devices.enumerate_cameras",
               return_value=[opencv_camera(0, PATH_A), opencv_camera(1, PATH_B)]), \
            patch.dict(sys.modules, {"_skellycam_rust": native}):
        response = client.post("/skellycam/camera/detect")

    assert response.status_code == 200
    cameras = {camera["index"]: camera for camera in response.json()["cameras"]}
    assert cameras[0]["path"] == PATH_A
    assert cameras[0]["supported_modes"] == [{"width": 1920, "height": 1200, "framerates": [60, 120]}]
    assert cameras[1]["path"] == PATH_B
    assert cameras[1]["supported_modes"] == [{"width": 640, "height": 480, "framerates": [30]}]


def test_camera_without_device_path_match_lists_no_modes():
    # Same index as the native camera, but no native device has this path.
    cameras = detect([opencv_camera(0, MSMF_PATH_A)],
                     native_module_returning([native_detection(0, PATH_A, [capture_format(640, 480, 30)])]))

    assert [camera.supported_modes for camera in cameras] == [[]]


def test_camera_with_empty_path_lists_no_modes():
    # A native device without a DevicePath is identified as "<name> " (trailing space).
    cameras = detect([opencv_camera(0, "")],
                     native_module_returning([native_detection(0, "", [capture_format(640, 480, 30)])]))

    assert [camera.supported_modes for camera in cameras] == [[]]


def test_supported_modes_list_mjpeg_resolutions_largest_first_with_sorted_unique_rates():
    formats = [
        capture_format(640, 480, 30), capture_format(640, 480, 60, "YUY2"), capture_format(1920, 1200, 120),
        capture_format(512, 512, 10), capture_format(2592, 1944, 5, "YUY2"), capture_format(1280, 720, 200),
        capture_format(1920, 1200, 10), capture_format(640, 480, 200), capture_format(1280, 960, 25),
        capture_format(640, 480, 30),
    ]
    cameras = detect([opencv_camera(0, PATH_A)], native_module_returning([native_detection(0, PATH_A, formats)]))

    assert [mode.model_dump() for mode in cameras[0].supported_modes] == [
        {"width": 1920, "height": 1200, "framerates": [10, 120]},
        {"width": 1280, "height": 960, "framerates": [25]},
        {"width": 1280, "height": 720, "framerates": [200]},
        {"width": 640, "height": 480, "framerates": [30, 200]},
        {"width": 512, "height": 512, "framerates": [10]},
    ]


def test_native_detection_failure_still_returns_cameras_without_modes():
    def failing_detection():
        raise RuntimeError("Camera detection failed: Cap_createContext returned null during detection")

    cameras = detect([opencv_camera(0, PATH_A), opencv_camera(1, PATH_B)],
                     SimpleNamespace(detect_cameras=failing_detection))

    assert [(camera.path, camera.supported_modes) for camera in cameras] == [(PATH_A, []), (PATH_B, [])]


def test_missing_native_module_still_returns_cameras_without_modes():
    # A None entry in sys.modules makes `import _skellycam_rust` raise ImportError.
    cameras = detect([opencv_camera(0, PATH_A)], None)

    assert [(camera.path, camera.supported_modes) for camera in cameras] == [(PATH_A, [])]
