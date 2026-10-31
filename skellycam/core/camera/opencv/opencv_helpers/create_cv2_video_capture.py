import logging
from collections.abc import Callable

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.determine_backend import determine_opencv_camera_backend
from skellycam.core.camera.opencv.opencv_helpers.opencv_apply_config import apply_camera_configuration
from skellycam.utilities.wait_functions import wait_1s
from skellycam.core.camera_group.camera_errors import CameraConnectionCancelled


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


logger = logging.getLogger(__name__)

# Minimum buffer size to reduce stale-frame latency.
# USB cameras deliver frames into an OS driver ring buffer (typically 2-4 frames deep).
# When our grab() loop falls behind, a larger buffer means we dequeue frames that were
# captured tens of milliseconds ago, making our grab timestamps a poor proxy for actual
# capture time. Setting this to 1 ensures grab() always returns the most recent frame
# the driver has available.
# NOTE: Not all backends honor this (MSMF ignores it). DSHOW on Windows does respect it.
_PREFERRED_BUFFER_SIZE = 1


def create_cv2_video_capture(
    config: CameraConfig,
    retry_count: int = 5,
    *,
    should_continue: Callable[[], bool] | None = None,
) -> tuple[cv2.VideoCapture, CameraConfig]:
    if retry_count < 0:
        raise ValueError("retry_count must be nonnegative")
    cap_backend = determine_opencv_camera_backend()
    context = f"camera {config.camera_id} (index {config.camera_index}, backend {cap_backend.name})"

    def check_cancelled() -> None:
        if should_continue is not None and not should_continue():
            raise CameraConnectionCancelled(f"Connection cancelled for {context}")

    for attempt in range(retry_count + 1):
        check_cancelled()
        capture = cv2.VideoCapture(int(config.camera_index), cap_backend.id)
        transferred = False
        try:
            if not capture.isOpened():
                raise FailedToOpenCameraException(f"Failed to open {context} on attempt {attempt + 1}/{retry_count + 1}")
            # Set fourcc, resolution, and framerate before the first read() so that the V4L2
            # driver negotiates the correct pixel format, frame size, and frame interval when
            # streaming begins.  Without this, the driver may default to a lower framerate
            # (e.g. 15fps instead of 30fps) or a format the camera cannot deliver, causing
            # select() timeouts or degraded performance.
            if config.capture_fourcc:
                capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*config.capture_fourcc))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.resolution.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.resolution.height)
            if config.framerate > 0:
                capture.set(cv2.CAP_PROP_FPS, config.framerate)

            # Minimize the driver-side frame buffer to reduce stale-frame latency.
            # This makes grab() timestamps a tighter proxy for actual frame capture time.
            if not capture.set(cv2.CAP_PROP_BUFFERSIZE, _PREFERRED_BUFFER_SIZE):
                logger.debug(
                    f"Camera {config.camera_index}: backend did not accept "
                    f"CAP_PROP_BUFFERSIZE={_PREFERRED_BUFFER_SIZE} (this is normal for some backends)"
                )
            else:
                actual = capture.get(cv2.CAP_PROP_BUFFERSIZE)
                logger.debug(f"Camera {config.camera_index}: buffer size set to {int(actual)}")

            check_cancelled()
            success, image = capture.read()
            if not success or image is None:
                raise FailedToReadFrameFromCameraException(
                    f"Failed to read initial frame from {context} on attempt {attempt + 1}/{retry_count + 1}"
                )
            check_cancelled()
            extracted_config = apply_camera_configuration(cv2_vid_capture=capture, prior_config=None, config=config)
            check_cancelled()
            logger.info(f"Created `cv2.VideoCapture` object for {context}")
            transferred = True
            return capture, extracted_config
        except (FailedToOpenCameraException, FailedToReadFrameFromCameraException) as error:
            if attempt == retry_count:
                raise
            logger.warning(f"{error}. Retrying...")
        finally:
            # Until a successful return, this function owns the capture, including
            # the final failed attempt and exceptions while applying settings.
            if not transferred:
                try:
                    capture.release()
                except Exception:
                    logger.exception(f"Failed to release {context} after connection failure")
        check_cancelled()
        wait_1s()
    raise AssertionError("Camera retry loop exited without a capture or an error")
