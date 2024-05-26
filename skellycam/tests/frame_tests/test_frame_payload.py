import numpy as np


def test_create_initial_frame(image_fixture: np.ndarray):
    # Arrange
    from skellycam.core import CameraId
    from skellycam.core.frames.frame_payload import FramePayload

    frame = FramePayload.create_initial_frame(camera_id=CameraId(0), image_shape=image_fixture.shape)
    assert not frame.hydrated
    assert frame.frame_number == 0
    assert frame.image_shape == image_fixture.shape


def test_create_frame_from_previous(frame_payload_fixture):
    # Arrange
    from skellycam.core.frames.frame_payload import FramePayload

    frame = FramePayload.from_previous(previous=frame_payload_fixture)

    # Assert
    assert frame.camera_id == frame_payload_fixture.camera_id
    assert frame.image_shape == frame_payload_fixture.image_shape
    assert frame.frame_number == frame_payload_fixture.frame_number + 1
    assert not frame.hydrated


def test_frame_payload_create_unhydrated_dummy(camera_id_fixture, image_fixture: np.ndarray):
    # Arrange
    from skellycam.core.frames.frame_payload import FramePayload

    frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id_fixture, image=image_fixture)

    # Assert
    assert frame.camera_id == camera_id_fixture
    assert frame.image_shape == image_fixture.shape
    assert frame.frame_number == 0
    assert not frame.hydrated


def test_frame_payload_to_and_from_buffer(frame_payload_fixture):
    # separate image from rest of frame payload, because that's how we put it into shm
    from skellycam.core.frames.frame_payload import FramePayload

    frame_wo_image = FramePayload(**frame_payload_fixture.model_dump(exclude={"image_data"}))
    assert not frame_wo_image.hydrated
    buffer = frame_wo_image.to_buffer(image=frame_payload_fixture.image)

    # Act
    recreated_frame = FramePayload.from_buffer(buffer=buffer, image_shape=frame_payload_fixture.image.shape)
    # Assert
    assert recreated_frame.image.shape == frame_payload_fixture.image.shape
    assert np.sum(recreated_frame.image - frame_payload_fixture.image) == 0


def test_frame_number_fixed_size(image_fixture: np.ndarray):
    # Arrange
    from skellycam.core.frames.frame_payload import FramePayload
    from skellycam.core import CameraId

    og_frame = FramePayload.create_initial_frame(camera_id=CameraId(0), image_shape=image_fixture.shape)
    assert not og_frame.hydrated
    assert og_frame.frame_number == 0
    og_frame_size = len(og_frame.to_buffer(image=image_fixture))

    for fr in range(int(1e5)):
        frame = FramePayload.create_initial_frame(camera_id=CameraId(0), image_shape=image_fixture.shape)
        frame.frame_number = fr
        frame_size = len(frame.to_buffer(image=image_fixture))
        assert frame_size == og_frame_size


def test_frame_number_int_to_bytes(frame_payload_fixture):
    from skellycam.core.frames.frame_payload import int_to_fixed_bytes

    assert frame_payload_fixture.frame_number_bytes == int_to_fixed_bytes(frame_payload_fixture.frame_number)
    from skellycam.core.frames.frame_payload import fixed_bytes_to_int

    assert frame_payload_fixture.frame_number == fixed_bytes_to_int(frame_payload_fixture.frame_number_bytes)
