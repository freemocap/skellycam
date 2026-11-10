"""DirectShow must receive frame rate first and FourCC last, once per change.

OpenCV 4.12's DirectShow backend restarts the stream for each frame-rate, size or FourCC setting, and
each restart forgets the previous request (references.bib: opencv412DirectShowSetup). The order of these
settings therefore decides which formats and frame rates a camera streams before the requested one.
"""
from unittest.mock import Mock, call

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.determine_backend import OpenCVBackend
from skellycam.core.camera.opencv.opencv_helpers import create_cv2_video_capture as creation
from skellycam.core.camera.opencv.opencv_helpers import opencv_apply_config as application

FORMAT_PROPERTIES = (cv2.CAP_PROP_FPS, cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FOURCC)
MJPG = cv2.VideoWriter.fourcc(*"MJPG")


def format_calls(capture):
    return [setting for setting in capture.set.call_args_list if setting.args[0] in FORMAT_PROPERTIES]


def fake_capture(backend_id):
    capture = Mock(spec=cv2.VideoCapture)
    capture.isOpened.return_value = True
    capture.set.return_value = True
    capture.get.return_value = float(backend_id)
    capture.read.return_value = (True, np.zeros((2, 2, 3), dtype=np.uint8))
    return capture


def open_with(monkeypatch, backend_id):
    capture = fake_capture(backend_id)
    monkeypatch.setattr(creation.cv2, "VideoCapture", Mock(return_value=capture))
    monkeypatch.setattr(creation, "determine_opencv_camera_backend",
                        lambda: OpenCVBackend(id=backend_id, name="test"))
    monkeypatch.setattr(application, "logger", Mock())
    config = CameraConfig(camera_id="cam0", camera_index=0, resolution={"width": 1280, "height": 720},
                          framerate=30.0, capture_fourcc="MJPG")
    monkeypatch.setattr(application, "extract_config_from_cv2_capture", lambda **kwargs: config)
    creation.create_cv2_video_capture(config)
    return capture


def test_directshow_open_sets_frame_rate_first_and_fourcc_last_once(monkeypatch):
    assert format_calls(open_with(monkeypatch, cv2.CAP_DSHOW)) == [
        call(cv2.CAP_PROP_FPS, 30.0), call(cv2.CAP_PROP_FRAME_WIDTH, 1280),
        call(cv2.CAP_PROP_FRAME_HEIGHT, 720), call(cv2.CAP_PROP_FOURCC, MJPG)]


def test_other_backends_keep_their_open_order(monkeypatch):
    assert format_calls(open_with(monkeypatch, cv2.CAP_V4L2)) == [
        call(cv2.CAP_PROP_FOURCC, MJPG), call(cv2.CAP_PROP_FRAME_WIDTH, 1280),
        call(cv2.CAP_PROP_FRAME_HEIGHT, 720), call(cv2.CAP_PROP_FPS, 30.0),
        call(cv2.CAP_PROP_FRAME_WIDTH, 1280), call(cv2.CAP_PROP_FRAME_HEIGHT, 720),
        call(cv2.CAP_PROP_FOURCC, MJPG)]


def test_directshow_resolution_change_sets_fourcc_after_size(monkeypatch):
    capture = fake_capture(cv2.CAP_DSHOW)
    monkeypatch.setattr(application, "logger", Mock())
    prior = CameraConfig(camera_id="cam0", camera_index=0, resolution={"width": 1280, "height": 720},
                         capture_fourcc="MJPG")
    config = prior.model_copy(update={"resolution": type(prior.resolution)(width=640, height=480)})
    monkeypatch.setattr(application, "extract_config_from_cv2_capture", lambda **kwargs: config)
    application.apply_camera_configuration(capture, prior, config)
    assert format_calls(capture) == [call(cv2.CAP_PROP_FRAME_WIDTH, 640), call(cv2.CAP_PROP_FRAME_HEIGHT, 480),
                                     call(cv2.CAP_PROP_FOURCC, MJPG)]

