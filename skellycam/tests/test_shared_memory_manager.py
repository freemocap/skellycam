from copy import deepcopy
from typing import Tuple

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager




@pytest.mark.asyncio
async def test_shared_memory_manager(camera_shared_memory_fixture):

    og_shm_manager = camera_shared_memory_fixture[0]
    child_shm_manager = camera_shared_memory_fixture[1]
    camera_configs = og_shm_manager.camera_configs
    number_of_frames_to_test = 10
    number_of_cameras = len(camera_configs)
    camera_ids = list(camera_configs.keys())
    mf_payload = MultiFramePayload.create(
        camera_ids=camera_ids,
        multi_frame_number=-1
    )

    for frame_number in range(number_of_frames_to_test):

        for camera_id, config in camera_configs.items():
            assert child_shm_manager.new_multi_frame_payload_available() is False
            assert og_shm_manager.new_multi_frame_payload_available() is False

            test_image = np.random.randint(0, 256, size=config.image_shape, dtype=np.uint8)
            frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                         image=test_image)

            cam_shm = child_shm_manager.get_camera_shared_memory(camera_id)
            cam_shm.put_frame(frame, test_image)

        assert og_shm_manager.new_multi_frame_payload_available() is True
        assert child_shm_manager.new_multi_frame_payload_available() is True

        mf_payload = await child_shm_manager.get_multi_frame_payload(payload=mf_payload)
        assert mf_payload.multi_frame_number == frame_number
        assert mf_payload.full
        assert mf_payload.hydrated
        assert len(mf_payload.frames) == number_of_cameras
