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
        frame = FramePayload.create_unhydrated_dummy(camera_id=camera_id,
                                                     image=image_fixture)
        original_camera_memory = og_manager.get_camera_shared_memory(camera_id)
        recreated_camera_memory = recreated_manager.get_camera_shared_memory(camera_id)

        # Check buffer sizes
        assert original_camera_memory.buffer_size == recreated_camera_memory.buffer_size

        # Debug statements to check the initial state of shared memory buffer
        print(f"Original buffer size: {original_camera_memory.buffer_size}")
        print(f"Recreated buffer size: {recreated_camera_memory.buffer_size}")

        # Put frame into original shared memory
        original_camera_memory.put_frame(image=image_fixture,
                                         frame=frame)

        print(f"After putting frame, shm.buf size: {len(original_camera_memory.shm.buf)}")
        print(f"Payload size: {original_camera_memory.payload_size}")

        # Retrieve frame from recreated shared memory
        retrieved_frame = recreated_camera_memory.retrieve_frame()

        # Assertions to check frame integrity
        assert retrieved_frame.model_dump(exclude={"image_data"}) == frame.model_dump(exclude={"image_data"})
        assert np.array_equal(retrieved_frame.image, image_fixture), "Image data mismatch"

        # Additional debug information if assertions fail
        if not np.array_equal(retrieved_frame.image, image_fixture):
            print(f"Expected image sum: {np.sum(image_fixture)}")
            print(f"Retrieved image sum: {np.sum(retrieved_frame.image)}")

        # Additional checks for buffer payload sizes
        original_full_payload_size = original_camera_memory.payload_size
        recreated_full_payload_size = recreated_camera_memory.payload_size
        assert original_full_payload_size == recreated_full_payload_size, (
            f"Payload size mismatch: Original ({original_full_payload_size}), "
            f"Recreated ({recreated_full_payload_size})"
        )

        # Clean up
        original_camera_memory.close()
        recreated_camera_memory.close()
