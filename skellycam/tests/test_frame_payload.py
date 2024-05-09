import time

import numpy as np

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload


def test_create_frame(image_fixture: np.ndarray) -> FramePayload:
    # Arrange
    frame = FramePayload.create_empty(camera_id=CameraId(0),
                                      image_shape=image_fixture.shape,
                                      frame_number=0)
    frame.image = image_fixture
    frame.previous_frame_timestamp_ns = time.perf_counter_ns()
    frame.timestamp_ns = time.perf_counter_ns()
    frame.success = True

    # Assert
    for key, value in frame.dict().items():
        assert value is not None, f"Key {key} is None"
    assert frame.hydrated
    assert frame.image_shape == image_fixture.shape
    assert np.sum(frame.image - image_fixture) == 0
    return frame


def test_frame_payload_to_and_from_buffer(image_fixture: np.ndarray):
    # Arrange
    frame = test_create_frame(image_fixture)
    buffer = frame.to_buffer(image=image_fixture)

    # Act
    recreated_frame = FramePayload.from_buffer(buffer=buffer,
                                               image_shape=image_fixture.shape)

    # Assert
    assert recreated_frame.hydrated
    assert np.sum(frame.image - image_fixture) == 0
