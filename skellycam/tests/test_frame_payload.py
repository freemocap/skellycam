import numpy as np

from skellycam.models.cameras.frames.frame_payload import FramePayload, RawImage, MultiFramePayload


def test_raw_image_to_and_from_bytes():
    image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    raw_image = RawImage.from_image(image)
    recovered_image = RawImage.from_bytes(raw_image.to_bytes())
    assert np.array_equal(image, recovered_image.get_image())


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
        np.frombuffer(original_payload.raw_image.image_bytes, dtype=np.uint8).reshape(
            original_payload.raw_image.height, original_payload.raw_image.width, original_payload.raw_image.channels),
        np.frombuffer(recovered_payload.raw_image.image_bytes, dtype=np.uint8).reshape(
            recovered_payload.raw_image.height, recovered_payload.raw_image.width,
            recovered_payload.raw_image.channels))


def test_multi_frame_payload_to_and_from_bytes():
    # Make a few  dummy image
    camera_ids = [0, 2, 1, 4]  # intentionally out of order and missing `3`
    original_multi_frame_payload = MultiFramePayload.create(camera_ids=camera_ids)

    for id in range(5):
        image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        original_multi_frame_payload.add_frame(
            FramePayload.create(success=True,
                                image=image,
                                timestamp_ns=123456789,
                                frame_number=10,
                                camera_id=id))

    assert original_multi_frame_payload.full, "MultiFramePayload didn't show 'full' after adding the frames, something is wrong!"

    # Convert to bytes
    multi_frame_bytes = original_multi_frame_payload.to_bytes()

    # Convert back to MultiFramePayload
    recovered_multi_frame_payload = MultiFramePayload.from_bytes(multi_frame_bytes)

    # Check that everything matches
    assert original_multi_frame_payload.camera_ids == recovered_multi_frame_payload.camera_ids
    assert original_multi_frame_payload.full == recovered_multi_frame_payload.full
    for camera_id in original_multi_frame_payload.camera_ids:
        assert np.array_equal(
            np.frombuffer(original_multi_frame_payload.frames[camera_id].raw_image.image_bytes,
                          dtype=np.uint8).reshape(
                original_multi_frame_payload.frames[camera_id].raw_image.height,
                original_multi_frame_payload.frames[camera_id].raw_image.width,
                original_multi_frame_payload.frames[camera_id].raw_image.channels),

            np.frombuffer(recovered_multi_frame_payload.frames[camera_id].raw_image.image_bytes,
                          dtype=np.uint8).reshape(
                recovered_multi_frame_payload.frames[camera_id].raw_image.height,
                recovered_multi_frame_payload.frames[camera_id].raw_image.width,
                recovered_multi_frame_payload.frames[camera_id].raw_image.channels)
        )


if __name__ == "__main__":
    test_raw_image_to_and_from_bytes()
    print("RawImage tests passed!")
    test_frame_payload_to_and_from_bytes()
    print("FramePayload tests passed!")
    test_multi_frame_payload_to_and_from_bytes()
    print("All tests passed!")
