import cv2

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig


def test_cv2_video_capture_mock(camera_config_fixture: CameraConfig,
                                mock_videocapture: cv2.VideoCapture):
    mock = cv2.VideoCapture(0)
    mock.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_config_fixture.image_shape[0])
    mock.set(cv2.CAP_PROP_FRAME_WIDTH, camera_config_fixture.image_shape[1])
    assert mock.isOpened()

    mock_success, mock_image = mock.read()
    assert mock_success
    assert mock_image.shape == camera_config_fixture.image_shape

    mock_success = mock.grab()
    assert mock_success
    assert mock.grab_called_count == 1

    mock_success, mock_image = mock.retrieve()
    assert mock_success
    assert mock_image.shape == camera_config_fixture.image_shape

    mock_success, mock_image = mock.retrieve()
    assert not mock_success
    assert mock_image is None

    mock.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    assert mock.get(cv2.CAP_PROP_FRAME_WIDTH) == 640

    mock.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    assert mock.get(cv2.CAP_PROP_FRAME_HEIGHT) == 480

    mock.set(cv2.CAP_PROP_FPS, 30)
    assert mock.get(cv2.CAP_PROP_FPS) == 30
