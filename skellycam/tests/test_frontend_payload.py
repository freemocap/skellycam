from skellycam.core.frames import multi_frame_payload
from skellycam.core.frames.frontend_image_payload import FrontendImagePayload


def test_frontend_image_payload_jpeg_compression(multi_frame_payload_fixture):
    payload_jpeg95 = FrontendImagePayload.from_multi_frame_payload(multi_frame_payload_fixture, jpeg_quality=95)
    payload_jpeg50 = FrontendImagePayload.from_multi_frame_payload(multi_frame_payload_fixture, jpeg_quality=50)
    assert all([len(jpeg) < len(jpeg50) for jpeg, jpeg50 in zip(payload_jpeg95.jpeg_images.values(), payload_jpeg50.jpeg_images.values())])

def test_to_and_from_msgpack(fronted_image_payload_fixture):
    msgpack_bytes = fronted_image_payload_fixture.to_msgpack()
    new_instance = FrontendImagePayload.from_msgpack(msgpack_bytes)
    assert new_instance == fronted_image_payload_fixture

