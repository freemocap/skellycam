import asyncio
import pickle
import time

import numpy as np


def test_frame_wrangler(camera_shared_memory_fixture,
                        multi_frame_payload_fixture: "MultiFramePayload",
                        camera_configs_fixture: "CameraConfigs", ):
    from skellycam.core.frames.frame_wrangler import FrameWrangler
    from skellycam.core.frames.frame_payload import FramePayload

    og_shm_manager = camera_shared_memory_fixture[0]
    child_shm_manager = camera_shared_memory_fixture[1]

    # create
    frame_wrangler = FrameWrangler()
    frame_wrangler.set_camera_configs(configs=camera_configs_fixture)
    frame_wrangler.start_frame_listener()

    number_of_frames_to_test = 10
    for frame_number in range(number_of_frames_to_test):
        for frame in multi_frame_payload_fixture.frames.values():
            unhydrated_bytes = frame.to_unhydrated_bytes()
            unhydrated_frame = FramePayload(**pickle.loads(unhydrated_bytes))
            frame_buffer = unhydrated_frame.to_buffer(image=frame.image)
            frame_wrangler.pipe_connection.send_bytes(frame_buffer)
        time.sleep(0.1)


    frame_wrangler.close()
