import multiprocessing

import numpy as np

from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


def test_original_shared_memory_manager_fixture(camera_configs_fixture,
                                                lock: multiprocessing.Lock = multiprocessing.Lock()
                                                ) -> CameraSharedMemoryManager:
    manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture, lock=lock)
    assert manager
    return manager


def test_recreate_shared_memory_manager_fixture(camera_configs_fixture,
                                                lock: multiprocessing.Lock = multiprocessing.Lock()
                                                ) -> CameraSharedMemoryManager:
    original_manager = test_original_shared_memory_manager_fixture(camera_configs_fixture, lock)
    recreated_manager = CameraSharedMemoryManager(camera_configs=camera_configs_fixture,
                                                  lock=lock,
                                                  existing_shared_memory_names=original_manager.shared_memory_names
                                                  )
    assert recreated_manager
    assert original_manager.shared_memory_names == recreated_manager.shared_memory_names
    assert original_manager._buffer_by_camera.keys() == recreated_manager._buffer_by_camera.keys()
    assert original_manager.total_buffer_size == recreated_manager.total_buffer_size
    return recreated_manager


def test_camera_memories(image_fixture, camera_configs_fixture):
    for config in camera_configs_fixture.values():
        config.resolution = ImageResolution.from_image(image_fixture)
        config.color_channels = image_fixture.shape[2] if len(image_fixture.shape) == 3 else 1
        assert config.image_shape == image_fixture.shape

    # Assert
    lock = multiprocessing.Lock()
    original_shared_memory_manager = test_original_shared_memory_manager_fixture(camera_configs_fixture, lock)
    recreated_shared_memory_manager = test_recreate_shared_memory_manager_fixture(camera_configs_fixture, lock)

    for camera_id in camera_configs_fixture.keys():
        frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                     image=image_fixture)
        original_camera_shared_memory = original_shared_memory_manager.get_camera_shared_memory(camera_id)
        recreated_camera_shared_memory = recreated_shared_memory_manager.get_camera_shared_memory(camera_id)
        assert original_camera_shared_memory.buffer_size == recreated_camera_shared_memory.buffer_size
        # put frame
        original_camera_shared_memory.put_frame(frame, image_fixture)
        # put another frame
        original_camera_shared_memory.put_frame(frame, image_fixture)
        assert original_camera_shared_memory.new_frame_available
        assert original_camera_shared_memory.last_frame_written_index == 1
        assert recreated_camera_shared_memory.new_frame_available
        assert recreated_camera_shared_memory.last_frame_written_index == 1

        # retrieve frame
        assert recreated_camera_shared_memory.frame_to_read == 0
        retrieved_frame = recreated_camera_shared_memory.get_next_frame()
        assert retrieved_frame.dict(exclude={"image_data"}) == frame.dict(exclude={"image_data"})
        assert np.sum(retrieved_frame.image) == np.sum(image_fixture)
        assert not recreated_camera_shared_memory.new_frame_available

        # retrieve another frame
        retrieved_frame2 = recreated_camera_shared_memory.get_next_frame()
        assert recreated_camera_shared_memory.frame_to_read == 1
        assert not recreated_camera_shared_memory.new_frame_available
        assert not original_camera_shared_memory.new_frame_available

        # test loop around
        for loop in range(256 * 2):
            original_camera_shared_memory.put_frame(frame, image_fixture)
            assert original_camera_shared_memory.new_frame_available
            assert original_camera_shared_memory.last_frame_written_index == loop % 256
            assert recreated_camera_shared_memory.new_frame_available
            assert recreated_camera_shared_memory.frame_to_read == loop % 256
            frame = recreated_camera_shared_memory.get_next_frame()
            assert frame == frame
