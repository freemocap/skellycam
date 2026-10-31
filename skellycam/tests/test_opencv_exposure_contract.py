"""Check backend control values and setting order, independently of webcam quirks."""
from unittest.mock import Mock, call

import cv2
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers import opencv_apply_config as application


@pytest.mark.parametrize(('mode', 'expected'), [('AUTO', 1.0), ('MANUAL', 0.0)])
def test_directshow_exposure_uses_boolean_control(mode, expected, monkeypatch):
    monkeypatch.setattr(application.sys, 'platform', 'win32')
    capture = Mock(spec=cv2.VideoCapture)
    capture.get.return_value = float(cv2.CAP_DSHOW)
    config = CameraConfig(camera_id='camera-A', camera_index=0, exposure_mode=mode, exposure=-6)
    application._apply_exposure(capture, config)
    assert capture.set.call_args_list[0] == call(cv2.CAP_PROP_AUTO_EXPOSURE, expected)
    if mode == 'MANUAL':
        assert capture.set.call_args_list[-1] == call(cv2.CAP_PROP_EXPOSURE, -6.0)


def test_exposure_is_applied_after_stream_format_changes(monkeypatch):
    monkeypatch.setattr(application, 'logger', Mock())
    capture = Mock(spec=cv2.VideoCapture)
    capture.isOpened.return_value = True
    capture.get.return_value = float(cv2.CAP_DSHOW)
    config = CameraConfig(camera_id='camera-A', camera_index=0, exposure_mode='MANUAL', exposure=-6)
    monkeypatch.setattr(application, 'extract_config_from_cv2_capture', lambda **kwargs: config)
    application.apply_camera_configuration(capture, None, config)
    assert capture.set.call_args_list[-1] == call(cv2.CAP_PROP_EXPOSURE, -6.0)
