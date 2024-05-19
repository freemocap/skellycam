

def test_from_multi_frame_payload(multi_frame_payload_fixture):
    frontend_image_payload = FrontendImagePayload.from_multi_frame_payload(multi_frame_payload, jpeg_quality=90)
    assert frontend_image_payload.multi_frame_number == 1
    assert 'cam1' in frontend_image_payload.jpeg_images

def test_to_msgpack():
    payload = FrontendImagePayload(jpeg_images={'cam1': b'image_data'}, utc_ns_to_perf_ns={'time1': 12345}, multi_frame_number=1)
    msgpack_data = payload.to_msgpack()
    assert isinstance(msgpack_data, bytes)

def test_from_msgpack():
    payload = FrontendImagePayload(jpeg_images={'cam1': b'image_data'}, utc_ns_to_perf_ns={'time1': 12345}, multi_frame_number=1)
    msgpack_data = payload.to_msgpack()
    new_payload = FrontendImagePayload.from_msgpack(msgpack_data)
    assert new_payload.jpeg_images == payload.jpeg_images
    assert new_payload.utc_ns_to_perf_ns == payload.utc_ns_to_perf_ns
    assert new_payload.multi_frame_number == payload.multi_frame_number

def test_get_item():
    payload = FrontendImagePayload(jpeg_images={'cam1': b'image_data'}, utc_ns_to_perf_ns={'time1': 12345}, multi_frame_number=1)
    assert payload['cam1'] == b'image_data'

def test_set_item():
    payload = FrontendImagePayload(jpeg_images={}, utc_ns_to_perf_ns={'time1': 12345}, multi_frame_number=1)
    payload['cam1'] = b'new_image_data'
    assert payload.jpeg_images == {'cam1': b'new_image_data'}

def test_str_representation():
    payload = FrontendImagePayload(jpeg_images={'cam1': b'image_data'}, utc_ns_to_perf_ns={'time1': 12345}, multi_frame_number=1)
    assert str(payload) == 'cam1: 10 bytes'