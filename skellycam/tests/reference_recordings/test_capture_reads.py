"""Real file-backed OpenCV capture through SkellyCam's production grab/retrieve helper."""

import time
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera.opencv.opencv_helpers.opencv_get_frame import opencv_get_frame
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from skellycam.tests.reference_recordings.datasets import SAMPLE, TEST, acquire


def frame_buffer(width, height):
    config = CameraConfig(camera_id="replay", camera_index=0,
                          resolution=ImageResolution(width=width, height=height))
    frame = np.zeros(1, dtype=create_frame_dtype(config)).view(np.recarray)
    frame.frame_metadata.camera_info = config.to_frame_camera_info()[0]
    frame.frame_metadata.frame_number[0] = -1
    return frame


@pytest.fixture(scope="module", params=[TEST, pytest.param(SAMPLE, marks=pytest.mark.sample_data)],
                ids=["test-222", "sample-1108"])
def reference(request):
    dataset = request.param
    return dataset, acquire(dataset)


@pytest.mark.real_data
@pytest.mark.parametrize("camera_index", [0, 1, 2], ids=["camera1", "camera2", "camera3"])
def test_capture_matches_video_frames_and_stops_at_eof(reference, camera_index):
    dataset, paths = reference
    path = paths[camera_index]
    capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    baseline = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
    try:
        assert capture.isOpened() and baseline.isOpened()
        width, height = int(baseline.get(cv2.CAP_PROP_FRAME_WIDTH)), int(baseline.get(cv2.CAP_PROP_FRAME_HEIGHT))
        assert (width, height) == (720, 1280)
        buffer = frame_buffer(width, height)
        previous_end = 0
        for index in range(dataset.frames):
            expected_ok, expected = baseline.read()
            assert expected_ok, f"Reference decode stopped at frame {index}"
            start = time.perf_counter_ns()
            success, actual = opencv_get_frame(capture, buffer)
            end = time.perf_counter_ns()
            assert success, f"Capture stopped at frame {index}"
            assert actual is buffer
            assert int(actual.frame_metadata.frame_number[0]) == index
            assert actual.image[0].shape == expected.shape
            assert actual.image.dtype == np.uint8
            # The production helper stamps camera/frame text near the top edge.
            # Compare the remaining pixels exactly to an independent decoder cursor.
            np.testing.assert_array_equal(actual.image[0, 80:], expected[80:])
            stamps = actual.frame_metadata.timestamps
            assert previous_end <= start <= stamps.pre_frame_grab_ns[0] <= stamps.post_frame_grab_ns[0]
            assert stamps.post_frame_grab_ns[0] <= stamps.pre_frame_retrieve_ns[0] <= stamps.post_frame_retrieve_ns[0] <= end
            previous_end = end
        assert not baseline.read()[0], "Recording contains more frames than declared"
        last_image = buffer.image.copy()
        for _ in range(2):
            assert not opencv_get_frame(capture, buffer)[0]
            assert int(buffer.frame_metadata.frame_number[0]) == dataset.frames - 1
            np.testing.assert_array_equal(buffer.image, last_image)
    finally:
        capture.release()
        baseline.release()
        assert not capture.isOpened() and not baseline.isOpened()
    assert not opencv_get_frame(capture, buffer)[0]
    assert int(buffer.frame_metadata.frame_number[0]) == dataset.frames - 1


@pytest.mark.parametrize("grab_succeeds", [False, True], ids=["grab-fails", "retrieve-fails"])
def test_failed_capture_does_not_advance_frame(grab_succeeds):
    capture = Mock(spec=cv2.VideoCapture)
    capture.grab.return_value = grab_succeeds
    capture.retrieve.return_value = (False, None)
    frame = frame_buffer(64, 48)
    frame.frame_metadata.frame_number[0] = 7
    frame.image[:] = 123
    try:
        success, returned = opencv_get_frame(capture, frame)
        assert not success
        assert returned is frame
        assert int(frame.frame_metadata.frame_number[0]) == 7
        assert np.all(frame.image == 123)
        assert capture.retrieve.call_count == int(grab_succeeds)
    finally:
        capture.release()
