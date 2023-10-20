import numpy as np

from skellycam.models.cameras.frames.frame_payload import FramePayload, RawImage


def test_raw_image_to_and_from_bytes():
    image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    raw_image = RawImage.from_cv2_image(image)
    recovered_image = RawImage.from_bytes(raw_image.to_bytes())
    assert np.array_equal(image, recovered_image.image)


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
        np.frombuffer(original_payload.raw_image.bytes, dtype=np.uint8).reshape(
            original_payload.raw_image.height, original_payload.raw_image.width, original_payload.raw_image.channels),
        np.frombuffer(recovered_payload.raw_image.bytes, dtype=np.uint8).reshape(
            recovered_payload.raw_image.height, recovered_payload.raw_image.width,
            recovered_payload.raw_image.channels))
