import multiprocessing

import numpy as np

from skellycam.core import CameraId
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


def test_camera_memories(image_fixture,
                         camera_configs_fixture,
                         ):
    for config in camera_configs_fixture.values():
        config.resolution = ImageResolution.from_image(image_fixture)
        config.color_channels = image_fixture.shape[2] if len(image_fixture.shape) == 3 else 1
        assert config.image_shape == image_fixture.shape

    # Assert
    lock = multiprocessing.Lock()
    manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture, lock=lock)
    assert manager
    recreated_manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture,
                                                  lock=lock,
                                                  existing_shared_memory_names=manager.shared_memory_names
                                                  )
    assert recreated_manager

    for camera_id in camera_configs_fixture.keys():
        frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                     image=image_fixture)
        original_camera_memory = manager.get_camera_shared_memory(camera_id)
        recreated_camera_memory = recreated_manager.get_camera_shared_memory(camera_id)
        assert original_camera_memory.buffer_size == recreated_camera_memory.buffer_size

        # put frame in loop a bunch of times, make sure it can handle wrapping around to the beginning
        try:
            for loop in range(256 * 2):
                unhydrated_frame = FramePayload.create_unhydrated_dummy(camera_id=CameraId(0),
                                                                        image=image_fixture)
                original_camera_memory.put_frame(unhydrated_frame, image_fixture)
                assert original_camera_memory.new_frame_available
                assert recreated_camera_memory.new_frame_available
                recreated_frame = recreated_camera_memory.get_next_frame()
                assert recreated_frame.dict(exclude={"image_data"}) == unhydrated_frame.dict(exclude={"image_data"})

        except Exception as e:
            print(f"Errorin loop {loop} - \n\n {type(e).__name__}: {e}")
            raise e






