from unittest.mock import MagicMock
import cv2
import numpy as np
from skellycam.core.cameras.config.camera_config import CameraConfig

def create_cv2_video_capture_mock(camera_config: CameraConfig) -> MagicMock:
    video_capture_mock = MagicMock(spec=cv2.VideoCapture)
    video_capture_mock.frame_grabbed = False
    video_capture_mock.is_opened = True

    def create_fake_image() -> np.ndarray:
        return np.random.randint(0, 255, camera_config.image_shape, dtype=np.uint8)

    def read() -> tuple[bool, np.ndarray]:
        return True, create_fake_image()

    def grab() -> bool:
        video_capture_mock.frame_grabbed = True
        return True

    def retrieve() -> tuple[bool, np.ndarray | None]:
        if video_capture_mock.frame_grabbed:
            video_capture_mock.frame_grabbed = False  # Reset the state
            return True, create_fake_image()
        else:
            return False, None

    def release() -> None:
        video_capture_mock.is_opened = False

    def isOpened() -> bool:
        return video_capture_mock.is_opened

    video_capture_mock.grab.side_effect = grab
    video_capture_mock.retrieve.side_effect = retrieve
    video_capture_mock.read.side_effect = read
    video_capture_mock.release.side_effect = release

    video_capture_mock.isOpened.side_effect = isOpened

    return video_capture_mock

def test_cv2_video_capture_mock() -> None:
    camera_config = CameraConfig(camera_id=0)
    mock = create_cv2_video_capture_mock(camera_config)
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

    mock.release()
    assert not mock.isOpened()
