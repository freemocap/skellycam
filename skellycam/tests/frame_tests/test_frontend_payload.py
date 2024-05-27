# from skellycam.core.frames.frontend_image_payload import FrontendImagePayload
#
#
# def test_frontend_image_payload_jpeg_compression(multi_frame_payload_fixture):
#     payload_jpeg95 = FrontendImagePayload.from_multi_frame_payload(multi_frame_payload_fixture, jpeg_quality=95)
#     payload_jpeg50 = FrontendImagePayload.from_multi_frame_payload(multi_frame_payload_fixture, jpeg_quality=50)
#     sizes_by_compression = {95: [], 50: []}
#     for camera_id in multi_frame_payload_fixture.camera_ids:
#         sizes_by_compression[95].append(len(payload_jpeg95.jpeg_images[camera_id]))
#         sizes_by_compression[50].append(len(payload_jpeg50.jpeg_images[camera_id]))
#
#     mean_size_95 = sum(sizes_by_compression[95]) / len(sizes_by_compression[95])
#     mean_size_50 = sum(sizes_by_compression[50]) / len(sizes_by_compression[50])
#     assert mean_size_95 > mean_size_50
#
#
# def test_to_and_from_msgpack(fronted_image_payload_fixture):
#     msgpack_bytes = fronted_image_payload_fixture.to_msgpack()
#     new_instance = FrontendImagePayload.from_msgpack(msgpack_bytes)
#     assert new_instance == fronted_image_payload_fixture
