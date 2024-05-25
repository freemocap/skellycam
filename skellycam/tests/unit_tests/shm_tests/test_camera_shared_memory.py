import pickle
from typing import Tuple

import numpy as np

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager


def test_camera_memories(camera_shared_memory_fixture: Tuple[CameraSharedMemoryManager, CameraSharedMemoryManager],
                         image_fixture: np.ndarray,
                         camera_configs_fixture: CameraConfigs):
    og_manager, recreated_manager = camera_shared_memory_fixture

    for camera_id in camera_configs_fixture.keys():
        og_unhydrated_frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                     image=image_fixture)
        original_camera_memory = og_manager.get_camera_shared_memory(camera_id)
        recreated_camera_memory = recreated_manager.get_camera_shared_memory(camera_id)

        # Check buffer sizes
        assert original_camera_memory.total_frame_buffer_size == recreated_camera_memory.total_frame_buffer_size, (
            f"Buffer size mismatch: Original ({original_camera_memory.total_frame_buffer_size}), "
            f"Recreated ({recreated_camera_memory.total_frame_buffer_size})"
        )

        # check shared memory names
        assert original_camera_memory.shared_memory_name == recreated_camera_memory.shared_memory_name, (
            f"Shared memory name mismatch: Original ({original_camera_memory.shared_memory_name}), "
            f"Recreated ({recreated_camera_memory.shared_memory_name})"
        )

        # check shared memory sizes
        assert original_camera_memory.shared_memory_size == recreated_camera_memory.shared_memory_size, (
            f"Shared memory size mismatch: Original ({original_camera_memory.shared_memory_size}), "
            f"Recreated ({recreated_camera_memory.shared_memory_size})"
        )

        # Put frame into original shared memory
        original_camera_memory.put_new_frame(image=image_fixture,
                                             frame=og_unhydrated_frame)


        # Retrieve image and frame bytes from original shared memory
        frame_buffer_mv = recreated_camera_memory.retrieve_frame()
        assert isinstance(frame_buffer_mv, memoryview)
        retrieved_frame = FramePayload.from_buffer(frame_buffer_mv, image_fixture.shape)
        # Assertions to check frame integrity
        assert retrieved_frame.hydrated, "Frame should not be hydrated"
        assert np.array_equal(retrieved_frame.image, image_fixture), "Image data mismatch"

        assert original_camera_memory.total_frame_buffer_size == recreated_camera_memory.total_frame_buffer_size, (
            f"Payload size mismatch: Original ({original_camera_memory.total_frame_buffer_size}), " 
            f"Recreated ({recreated_camera_memory.total_frame_buffer_size})"
        )

