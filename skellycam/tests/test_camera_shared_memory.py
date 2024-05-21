import multiprocessing

import numpy as np

from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


def test_camera_memories(image_fixture, camera_configs_fixture):
    for config in camera_configs_fixture.values():
        config.resolution = ImageResolution.from_image(image_fixture)
        config.color_channels = image_fixture.shape[2] if len(image_fixture.shape) == 3 else 1
        assert config.image_shape == image_fixture.shape

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
        # put frame
        original_camera_memory.put_frame(frame, image_fixture)

        # put another frame
        original_camera_memory.put_frame(frame, image_fixture)
        assert original_camera_memory.new_frame_available
        assert original_camera_memory.last_frame_written_index == 1

        assert recreated_camera_memory.new_frame_available
        assert recreated_camera_memory.last_frame_written_index == 1

        # retrieve frame
        assert recreated_camera_memory.read_next == 0
        retrieved_frame = recreated_camera_memory.get_next_frame()
        assert recreated_camera_memory.read_next == 1
        assert retrieved_frame.dict(exclude={"image_data"}) == frame.dict(exclude={"image_data"})
        assert np.sum(retrieved_frame.image) == np.sum(image_fixture)
        assert recreated_camera_memory.new_frame_available

        # retrieve another frame
        retrieved_frame2 = recreated_camera_memory.get_next_frame()
        assert recreated_camera_memory.read_next == 2
        assert not recreated_camera_memory.new_frame_available
        assert not original_camera_memory.new_frame_available


def test_camera_memories_wrap_around(image_fixture,
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
        original_camera_memory = manager.get_camera_shared_memory(camera_id)
        recreated_camera_memory = recreated_manager.get_camera_shared_memory(camera_id)
        assert original_camera_memory.buffer_size == recreated_camera_memory.buffer_size

        # put frame in loop a bunch of times, make sure it can handle wrapping around to the beginning
        try:
            for loop in range(255 * 3):
                if loop % 256 == 0:
                    print(f"Loop: {loop}")
                test_image = np.random.randint(0, 255, size=image_fixture.shape, dtype=np.uint8)
                original_frame = FramePayload.create_unhydrated_dummy(camera_id=CameraId(0),
                                                                        image=test_image)
                original_frame.frame_number = loop
                original_camera_memory.put_frame(original_frame, test_image)
                assert original_camera_memory.new_frame_available
                assert recreated_camera_memory.new_frame_available
                recreated_frame = recreated_camera_memory.get_next_frame()
                assert recreated_frame.frame_number == loop
                assert recreated_frame.frame_number == original_frame.frame_number
                assert np.sum(recreated_frame.image - test_image) == 0
                assert recreated_frame.dict(exclude={"image_data"}) == original_frame.dict(exclude={"image_data"})
        except Exception as e:
            print(f"Error in loop {loop}")
            raise e
