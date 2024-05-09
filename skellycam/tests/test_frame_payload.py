import logging
import time

import numpy as np
import pytest

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


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
    assert frame.dict() == recreated_frame.dict()


def test_frame_payload_bad_buffer_reject(image_fixture: np.ndarray):
    frame = test_create_frame(image_fixture)
    buffer = frame.to_buffer(image=image_fixture)

    recreated_frame = FramePayload.from_buffer(buffer=buffer,
                                               image_shape=image_fixture.shape)
    assert isinstance(recreated_frame, FramePayload)

    bad_buffer_start = memoryview(bytes([buffer[0] + 1]) + buffer[1:])  # absolute garbage buffer
    with pytest.raises(ValueError, match="mismatch"):
        FramePayload.from_buffer(buffer=bad_buffer_start,
                                 image_shape=image_fixture.shape)

    bad_buffer_end = memoryview(bytes(buffer[:-1]) + bytes([buffer[-1] + 1]))  # a true embarrassment
    with pytest.raises(ValueError, match="mismatch"):
        FramePayload.from_buffer(buffer=bad_buffer_end,
                                 image_shape=image_fixture.shape)

    for _ in range(10):
        random_index = np.random.randint(0, len(buffer))  # an utter disgrace
        bad_buffer_rand = memoryview(
            bytes(buffer[:random_index]) +
            bytes([buffer[random_index] + 1]) +
            bytes(buffer[random_index + 1:]))

        with pytest.raises(ValueError, match="mismatch"):
            FramePayload.from_buffer(buffer=bad_buffer_rand,
                                     image_shape=image_fixture.shape)
