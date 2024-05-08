import numpy as np
import pytest

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload


def create_test_image(height: int, width: int, color_channels: int) -> np.ndarray:
    return np.random.randint(0, 256, size=(height, width, color_channels), dtype=np.uint8)


def test_frame_payload_create_empty():
    # Test FramePayload creation with `create_empty` method
    camera_id = CameraId(0)
    frame_number = 0
    frame = FramePayload.create_empty(camera_id=camera_id, frame_number=frame_number)
    assert frame.camera_id == camera_id
    assert frame.frame_number == frame_number


def test_frame_payload_create_dummy():
    # Test FramePayload creation with `create_dummy` method
    frame = FramePayload.create_dummy()
    assert frame.dummy == True


def test_frame_payload_to_and_from_buffer():
    # Test FramePayload creation from buffer
    # Arrange
    image_shape = (48, 64, 3)
    dummy_image = create_test_image(*image_shape)

    dummy_frame = FramePayload.create_dummy()
    assert dummy_frame.hydrated == False

    unhydrated_bytes = dummy_frame.to_unhydrated_bytes()
    image_bytes = dummy_image.tobytes()
    buffer = memoryview(unhydrated_bytes + image_bytes)

    # Act
    frame = FramePayload.from_buffer(buffer=buffer,
                                     image_shape=image_shape)

    # Assert
    assert dummy_frame.hydrated == False
    assert frame.image_data == image_bytes
    assert frame.image_shape == image_shape
    assert unhydrated_bytes == frame.to_unhydrated_bytes()
    assert buffer == frame.to_buffer()

#
# def test_frame_payload_bad_buffer_reject():
#     dummy_frame = FramePayload.create_dummy()
#     image_shape = (48, 64, 3)
#     test_image = create_test_image(*image_shape)
#     image_bytes = test_image.tobytes()
#     unhydrated_buffer = dummy_frame.to_unhydrated_bytes()
#     buffer = memoryview(unhydrated_buffer + image_bytes)
#
#     recreated_frame = FramePayload.from_buffer(buffer=buffer,
#                                                image_shape=image_shape)
#     assert isinstance(recreated_frame, FramePayload)
#
#
#     bad_image_bytes = bytes([image_bytes[0] + 1]) + image_bytes[1:]
#     #TODO - come up with a way to make it fail if the `unhydrated_buffer` is modified
#     bad_unhydrated_buffer = bytes([unhydrated_buffer[0] + 1]) + unhydrated_buffer[1:]
#     assert not bad_unhydrated_buffer == unhydrated_buffer
#     assert not bad_image_bytes == image_bytes
#
#     bad_buffer = memoryview(bytes([unhydrated_buffer[0] + 1]) + unhydrated_buffer[1:] + bad_image_bytes)
#     with pytest.raises(ValueError, match="mismatch"):
#         FramePayload.from_buffer(buffer=bad_buffer,
#                                  image_shape=image_shape)
#
#
#
#
#
