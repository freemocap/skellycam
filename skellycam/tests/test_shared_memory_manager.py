import pickle
from typing import Tuple

import numpy as np
import pytest

from skellycam.core.frames.frame_payload import FramePayload


def test_shared_memory_manager(
        camera_shared_memory_fixture: Tuple["CameraSharedMemoryManager", "CameraSharedMemoryManager"]):
    og_shm_manager = camera_shared_memory_fixture[0]
    child_shm_manager = camera_shared_memory_fixture[1]
    camera_configs = og_shm_manager.camera_configs
    number_of_frames_to_test = 10

    for frame_number in range(number_of_frames_to_test):

        for camera_id, config in camera_configs.items():
            test_image = np.random.randint(0, 256, size=config.image_shape, dtype=np.uint8)
            unhydrated_frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                         image=test_image)

            cam_shm = child_shm_manager.get_camera_shared_memory(camera_id)
            cam_shm.put_new_frame(image=test_image, frame=unhydrated_frame)
            image_bytes, frame_bytes = cam_shm.retrieve_frame()
            unhydrated_frame_dict = pickle.loads(frame_bytes)
            unhydrated_frame = FramePayload(**unhydrated_frame_dict)
            assert not unhydrated_frame.hydrated
            image = unhydrated_frame.image_from_bytes(image_bytes)
            assert np.array_equal(image, test_image)
