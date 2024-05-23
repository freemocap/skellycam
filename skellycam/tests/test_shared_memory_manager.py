import pickle

import numpy as np
import pytest

from skellycam.core.frames.frame_payload import FramePayload


@pytest.mark.asyncio
async def test_shared_memory_manager(camera_shared_memory_fixture):
    og_shm_manager = camera_shared_memory_fixture[0]
    child_shm_manager = camera_shared_memory_fixture[1]
    camera_configs = og_shm_manager.camera_configs
    number_of_frames_to_test = 10

    for frame_number in range(number_of_frames_to_test):

        for camera_id, config in camera_configs.items():

            test_image = np.random.randint(0, 256, size=config.image_shape, dtype=np.uint8)
            frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                         image=test_image)

            cam_shm = child_shm_manager.get_camera_shared_memory(camera_id)
            cam_shm.put_frame(image=test_image, frame=frame)
            image_bytes, frame_bytes = cam_shm.retrieve_frame()
            frame_dict = pickle.loads(frame_bytes)
            frame = FramePayload(**frame_dict)
            assert frame.image.shape == test_image.shape
            image = frame.image_from_bytes(image_bytes)
            assert np.array_equal(image, test_image)
