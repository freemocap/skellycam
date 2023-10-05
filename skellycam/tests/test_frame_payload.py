# import numpy as np
# import pytest
#
# from skellycam.data_models.frame_payload import SharedMemoryFramePayload, FramePayload
#
#
# def test_frame_payload_from_shared_memory_frame_payload():
#     shared_frame_payload = SharedMemoryFramePayload.from_data(
#         success=True,
#         image=np.zeros((5, 5, 3)),
#         timestamp_ns=123456,
#         camera_id="test",
#         number_of_frames_received=789
#     )
#     frame_payload = FramePayload.from_shared_memory_frame_payload(shared_frame_payload)
#
#     assert np.all(frame_payload.timestamp_ns == shared_frame_payload.timestamp_ns.value), f"Timestamps don't match: {frame_payload.timestamp_ns} != {shared_frame_payload.timestamp_ns.value}"
#     assert np.all(frame_payload.image == shared_frame_payload.get_image()), f"Images don't match: (Image shapes are - {frame_payload.image.shape} != {shared_frame_payload.get_image().shape})"
#     assert frame_payload.success == shared_frame_payload.success.value, f"Success flags don't match: {frame_payload.success} != {shared_frame_payload.success.value}"
#     assert frame_payload.camera_id == shared_frame_payload.camera_id.value, f"Camera IDs don't match: {frame_payload.camera_id} != {shared_frame_payload.camera_id.value}"
#     assert frame_payload.number_of_frames_received == shared_frame_payload.number_of_frames_received.value, f"Number of frames received don't match: {frame_payload.number_of_frames_received} != {shared_frame_payload.number_of_frames_received.value}"
#
# def test_shared_memory_frame_payload_from_data():
#     timestamp_ns = 123456
#     image = np.zeros((5, 5, 3))
#     camera_id = "test"
#     number_of_frames_received = 789
#     shared_frame_payload = SharedMemoryFramePayload.from_data(
#         success=True,
#         image=image,
#         timestamp_ns=timestamp_ns,
#         camera_id=camera_id,
#         number_of_frames_received=number_of_frames_received
#     )
#     assert np.all(shared_frame_payload.timestamp_ns.value == timestamp_ns), f"Timestamps don't match: {shared_frame_payload.timestamp_ns.value} != {timestamp_ns}"
#     assert np.all(shared_frame_payload.get_image() == image), f"Images don't match: (Image shapes are - {shared_frame_payload.get_image().shape} != {image.shape})"
#     assert shared_frame_payload.success.value == True, f"Success flags don't match: {shared_frame_payload.success.value} != {True}"
#     assert shared_frame_payload.camera_id.value == camera_id, f"Camera IDs don't match: {shared_frame_payload.camera_id.value} != {camera_id}"
#     assert shared_frame_payload.number_of_frames_received.value == number_of_frames_received, f"Number of frames received don't match: {shared_frame_payload.number_of_frames_received.value} != {number_of_frames_received}"
#
#
#
# def test_shared_memory_frame_payload_make_shared_memory_image():
#     image = np.zeros((5, 5, 3))
#     shared_img, shape, dtype = SharedMemoryFramePayload.make_shared_memory_image(image)
#
#     assert shared_img.shape == shape, f"Shapes don't match: {shared_img.shape} != {shape}"
#     assert shared_img.dtype == dtype, f"Data types don't match: {shared_img.dtype} != {dtype}"
#     assert np.all(shared_img == image), f"Images don't match: (Image shapes are - {shared_img.shape} != {image.shape})"
#
#
# def test_shared_memory_frame_payload_get_image():
#     shared_frame_payload = SharedMemoryFramePayload.from_data(
#         timestamp_ns=123456,
#         image=np.zeros((5, 5, 3)),
#         camera_id="test",
#         number_of_frames_received=789
#     )
#     image = shared_frame_payload.get_image()
#     assert np.all(image == np.zeros((5, 5, 3))), f"Images don't match: (Image shapes are - {image.shape} != {(5, 5, 3)})"
#
#
# def test_shared_memory_frame_payload_unlink():
#     shared_frame_payload = SharedMemoryFramePayload.from_data(
#         timestamp_ns=123456,
#         image=np.zeros((5, 5, 3)),
#         camera_id="test",
#         number_of_frames_received=789
#     )
#     shared_frame_payload.unlink()
#
#     with pytest.raises(Exception):
#         _ = shared_frame_payload.get_image()
