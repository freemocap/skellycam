import numpy as np
import pytest

from skellycam.data_models.frame_payload import SharedMemoryFramePayload, FramePayload


@pytest.fixture
def sample_image():
    return np.random.randint(0, 255, (10, 20, 3), dtype=np.uint8)


def test_frame_payload_conversion(sample_image):
    shared_payload = SharedMemoryFramePayload.from_data(success=True,
                                                        image=sample_image,
                                                        timestamp_ns=123456789,
                                                        camera_id="test_camera",
                                                        number_of_frames_received=1)
    final_payload = FramePayload.from_shared_memory_frame_payload(shared_memory_frame_payload=shared_payload)

    assert np.array_equal(shared_payload.get_image(), final_payload.image)
    assert shared_payload.success == final_payload.success
    assert shared_payload.timestamp_ns == final_payload.timestamp
    assert shared_payload.camera_id == final_payload.camera_id
    assert shared_payload.frames_received == final_payload.frames_received
