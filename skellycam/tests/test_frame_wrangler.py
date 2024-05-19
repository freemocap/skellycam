import asyncio

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.frame_wrangler import FrameWrangler


@pytest.mark.asyncio
async def test_frame_wrangler(camera_shared_memory_fixture,
                              camera_configs_fixture: CameraConfigs, ):
    og_shm_manager = camera_shared_memory_fixture[0]
    child_shm_manager = camera_shared_memory_fixture[1]

    # create
    frame_wrangler = FrameWrangler()
    frame_wrangler.set_camera_configs(camera_configs=camera_configs_fixture,
                                      shared_memory_manager=og_shm_manager)
    frame_wrangler.start_frame_listener()

    number_of_frames_to_test = 10
    for frame_number in range(number_of_frames_to_test):
        await asyncio.sleep(0.1)
        assert not child_shm_manager.new_multi_frame_payload_available()
        assert not og_shm_manager.new_multi_frame_payload_available()
        for camera_id, config in camera_configs_fixture.items():
            test_image = np.random.randint(0, 256, size=config.image_shape, dtype=np.uint8)
            frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                         image=test_image)

            cam_shm = child_shm_manager.get_camera_shared_memory(camera_id)
            cam_shm.put_frame(frame, test_image)
        assert frame_wrangler.multi_frames_received == frame_number

    await frame_wrangler.close()
