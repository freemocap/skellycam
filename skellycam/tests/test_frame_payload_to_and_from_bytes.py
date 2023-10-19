import numpy as np

from skellycam.models.cameras.frames.frame_payload import FramePayload


def test_frame_payload_to_and_from_bytes():
    # Make a dummy image
    image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

    # Create a FramePayload
    original_payload = FramePayload.create(
        success=True, image=image, timestamp_ns=123456789, frame_number=10, camera_id=2)

    # Convert to bytes
    byte_obj = original_payload.to_bytes()

    # Convert back to FramePayload
    recovered_payload = FramePayload.from_bytes(byte_obj)

    # Check that everything matches
    assert original_payload.success == recovered_payload.success
    assert original_payload.timestamp_ns == recovered_payload.timestamp_ns
    assert original_payload.frame_number == recovered_payload.frame_number
    assert original_payload.camera_id == recovered_payload.camera_id
    assert np.array_equal(
        np.frombuffer(original_payload.image.bytes, dtype=np.uint8).reshape(
            original_payload.image.height, original_payload.image.width, original_payload.image.channels),
        np.frombuffer(recovered_payload.image.bytes, dtype=np.uint8).reshape(
            recovered_payload.image.height, recovered_payload.image.width, recovered_payload.image.channels))
