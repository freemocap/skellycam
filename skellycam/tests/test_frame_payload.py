import time

import numpy as np

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload


def test_create_frame(image_fixture: np.ndarray):
    # Arrange
    frame = FramePayload.create_empty(camera_id=CameraId(0),
                                      image_shape=image_fixture.shape,
                                      frame_number=0)
    frame.image = image_fixture
    frame.previous_frame_timestamp_ns = time.perf_counter_ns()
    frame.timestamp_ns = time.perf_counter_ns()
    frame.success = True
    assert frame.hydrated == True


def test_frame_payload_create_empty(image_fixture: np.ndarray):
    # Arrange
    frame = FramePayload.create_empty(camera_id=CameraId(0),
                                      image_shape=image_fixture.shape,
                                      frame_number=0)

    # Assert
    assert frame.camera_id == CameraId(0)
    assert frame.image_shape == image_fixture.shape
    assert frame.frame_number == 0
    assert frame.color_channels == 3
    assert frame.hydrated == False


def test_frame_payload_create_hydrated_dummy(image_fixture: np.ndarray):
    # Arrange
    frame = FramePayload.create_hydrated_dummy(image=image_fixture)

    # Assert
    assert frame.camera_id == CameraId(0)
    assert frame.image_shape == image_fixture.shape
    assert frame.frame_number == 0
    assert frame.color_channels == 3
    assert frame.hydrated == True


def test_frame_payload_create_unhydrated_dummy(image_fixture: np.ndarray):
    # Arrange
    frame = FramePayload.create_unhydrated_dummy(camera_id=CameraId(0),
                                                 image=image_fixture)

    # Assert
    assert frame.camera_id == CameraId(0)
    assert frame.image_shape == image_fixture.shape
    assert frame.frame_number == 0
    assert frame.color_channels == 3
    assert frame.hydrated == False

    frame_buffer = frame.to_buffer(image=image_fixture)
    re_frame = frame.from_buffer(buffer=frame_buffer,
                                 image_shape=image_fixture.shape)

    assert frame == re_frame


def test_frame_from_previous(frame_fixture):
    # Act
    frame = FramePayload.from_previous(previous=frame_fixture)

    # Assert
    assert frame.camera_id == frame_fixture.camera_id
    assert frame.image_shape == frame_fixture.image_shape
    assert frame.frame_number == frame_fixture.frame_number + 1
    assert frame.color_channels == frame_fixture.color_channels
    assert frame.hydrated == False


def test_frame_payload_to_and_from_buffer(frame_fixture):
    # separate image from rest of frame payload, because that's how we put it into shm
    frame_wo_image = FramePayload(**frame_fixture.dict(exclude={"image_data"}))
    assert not frame_wo_image.hydrated
    buffer = frame_wo_image.to_buffer(image=frame_fixture.image)

    # Act
    recreated_frame = FramePayload.from_buffer(buffer=buffer,
                                               image_shape=frame_fixture.image.shape)

    # Assert
    assert recreated_frame == frame_fixture
    assert np.sum(recreated_frame.image - frame_fixture.image) == 0
