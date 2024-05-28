import time
from typing import Optional
from unittest.mock import MagicMock

import cv2
import numpy as np
from scipy.stats import gamma

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.default_config import DEFAULT_FRAME_RATE


def create_cv2_video_capture_mock(camera_config: CameraConfig) -> MagicMock:
    video_capture_mock = MagicMock(spec=cv2.VideoCapture)
    video_capture_mock.frame_grabbed = False
    video_capture_mock.is_opened = True
    video_capture_mock.properties = {}

    def gamma_delay(mean_delay: float) -> float:
        """
        Generate a Gamma-distributed delay where the standard deviation is half the mean.

        Args:
            mean_delay (float): The mean delay in seconds.

        Returns:
            float: The Gamma-distributed delay in seconds.
        """
        shape = 4  # k
        scale = mean_delay / shape  # θ
        return float(gamma.rvs(a=shape, scale=scale))

    def simulate_frame_grab_delay() -> None:
        """
        Simulate a delay for a 30fps camera with a Gamma-distributed delay where the standard deviation is half the mean.

        This function simulates the delay for a 30fps camera.

        The Machine said:
        ```
        If the variability (in this case, the standard deviation) is half the mean, the distribution is no longer Poisson, as the Poisson distribution has the property that its mean and variance are equal. Instead, this scenario might describe a distribution where the standard deviation is proportional to the mean, but with a specific proportionality constant.

        One such distribution that can exhibit this property is the **Gamma distribution**. In a Gamma distribution with shape parameter \( k \) and scale parameter \( \theta \), the mean \( \mu \) is given by \( k\theta \) and the variance \( \sigma^2 \) is given by \( k\theta^2 \). The standard deviation \( \sigma \) would then be \( \sqrt{k}\theta \). If you want the standard deviation to be half the mean, you would set this relationship up as follows:

        \[ \sigma = \frac{\mu}{2} \]

        Given \( \mu = k\theta \) and \( \sigma = \sqrt{k}\theta \), we can substitute:

        \[ \sqrt{k}\theta = \frac{k\theta}{2} \]

        Solving for \( k \):

        \[ \sqrt{k} = \frac{k}{2} \]
        \[ 2\sqrt{k} = k \]
        \[ k = 4 \]

        So, if you set the shape parameter \( k \) to 4, and the scale parameter \( \theta \) to \( \frac{\mu}{4} \), you will achieve a distribution where the standard deviation is half the mean.

        ```
        ...and it looks right ish to me lol
        """
        ideal_frame_duration = 1 / DEFAULT_FRAME_RATE
        delay = gamma_delay(ideal_frame_duration)
        time.sleep(delay)  # Simulate the delay

    def create_fake_image() -> np.ndarray:
        simulate_frame_grab_delay()
        return np.random.randint(0, 255, camera_config.image_shape, dtype=np.uint8)

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
            video_capture_mock.frame_grabbed = False  # Reset the state
            return True, create_fake_image()
        else:
            return False, None

    def release() -> None:
        video_capture_mock.is_opened = False

    def isOpened() -> bool:
        return video_capture_mock.is_opened

    def set(prop_id: int, value: float) -> bool:
        # TODO - figure out what happens if we try to set a property that doesn't exist or on a closed camera
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

    mock.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    assert mock.get(cv2.CAP_PROP_FRAME_WIDTH) == 640

    mock.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    assert mock.get(cv2.CAP_PROP_FRAME_HEIGHT) == 480

    mock.set(cv2.CAP_PROP_FPS, 30)
    assert mock.get(cv2.CAP_PROP_FPS) == 30


def test_cv2_video_capture_mock_fps() -> None:
    camera_config = CameraConfig(camera_id=0)
    mock = create_cv2_video_capture_mock(camera_config)
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
