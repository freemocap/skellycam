import time
from typing import Optional
from unittest.mock import MagicMock

import cv2
import numpy as np
from scipy.stats import gamma

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.default_config import DEFAULT_FRAME_RATE


def create_cv2_video_capture_magic_mock(camera_config_fixture: CameraConfig) -> MagicMock:
    video_capture_mock = MagicMock(spec=cv2.VideoCapture)
    video_capture_mock.frame_grabbed = False
    video_capture_mock.is_opened = True
    video_capture_mock.properties = {}

    def gamma_delay(mean_delay: float) -> float:
        shape = 4
        scale = mean_delay / shape
        return float(gamma.rvs(a=shape, scale=scale))

    def simulate_frame_grab_delay() -> None:
        ideal_frame_duration = 1 / DEFAULT_FRAME_RATE
        delay = gamma_delay(ideal_frame_duration)
        time.sleep(delay)

    def create_fake_image() -> np.ndarray:
        simulate_frame_grab_delay()
        return np.random.randint(0, 255, camera_config_fixture.image_shape, dtype=np.uint8)

    def read() -> tuple[bool, Optional[np.ndarray]]:
        if not video_capture_mock.isOpened():
            return False, None
        return True, create_fake_image()

    def grab() -> bool:
        if not video_capture_mock.isOpened():
            return False
        video_capture_mock.frame_grabbed = True
        return True

    def retrieve() -> tuple[bool, Optional[np.ndarray]]:
        if not video_capture_mock.isOpened():
            return False, None
        if video_capture_mock.frame_grabbed:
            video_capture_mock.frame_grabbed = False
            return True, create_fake_image()
        else:
            return False, None

    def release() -> None:
        video_capture_mock.is_opened = False

    def isOpened() -> bool:
        return video_capture_mock.is_opened

    def set(prop_id: int, value: float) -> bool:
        video_capture_mock.properties[prop_id] = value
        return True

    def get(prop_id: int) -> float:
        return float(video_capture_mock.properties.get(prop_id, 0.0))

    video_capture_mock.grab.side_effect = grab
    video_capture_mock.retrieve.side_effect = retrieve
    video_capture_mock.read.side_effect = read
    video_capture_mock.release.side_effect = release
    video_capture_mock.get.side_effect = get
    video_capture_mock.set.side_effect = set
    video_capture_mock.isOpened.side_effect = isOpened

    return video_capture_mock

def test_cv2_video_capture_mock() -> None:
    camera_config = CameraConfig(camera_id=0)
    mock = create_cv2_video_capture_magic_mock(camera_config)
    assert mock.isOpened()

    mock_success, mock_image = mock.read()
    assert mock_success
    assert mock_image.shape == camera_config.image_shape

    mock_success = mock.grab()
    assert mock_success

    mock_success, mock_image = mock.retrieve()
    assert mock_success
    assert mock_image.shape == camera_config.image_shape

    mock_success, mock_image = mock.retrieve()
    assert not mock_success
    assert mock_image is None

    mock.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    assert mock.get(cv2.CAP_PROP_FRAME_WIDTH) == 640

    mock.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    assert mock.get(cv2.CAP_PROP_FRAME_HEIGHT) == 480

    mock.set(cv2.CAP_PROP_FPS, 30)
    assert mock.get(cv2.CAP_PROP_FPS) == 30

def test_cv2_video_capture_mock_fps() -> None:
    camera_config = CameraConfig(camera_id=0)
    mock = create_cv2_video_capture_magic_mock(camera_config)
    mock.set(cv2.CAP_PROP_FPS, 30)
    assert mock.get(cv2.CAP_PROP_FPS) == 30
    timestamps = []
    for _ in range(100):
        mock.read()
        timestamps.append(time.perf_counter())
    frame_durations = np.diff(timestamps)
    mean_frame_duration_s = np.mean(frame_durations)
    std_dev_frame_duration_s = np.std(frame_durations)
    ideal_frame_duration_s = 1 / 30

    assert np.isclose(mean_frame_duration_s, ideal_frame_duration_s, atol=ideal_frame_duration_s)
    assert np.isclose(std_dev_frame_duration_s, ideal_frame_duration_s / 2, atol=ideal_frame_duration_s / 2)
    print(f"\t\tMean frame duration: {mean_frame_duration_s:.3f}s ± {std_dev_frame_duration_s:.3f}s")

    mock.release()
    assert not mock.isOpened()

    mock_success, mock_image = mock.read()
    assert not mock_success
    assert mock_image is None

    mock_success = mock.grab()
    assert not mock_success

    mock_success, mock_image = mock.retrieve()
    assert not mock_success