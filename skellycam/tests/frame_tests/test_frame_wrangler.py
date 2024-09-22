import multiprocessing

import numpy as np

from skellycam.core.cameras.group import CameraGroupOrchestrator
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory


def test_frame_wrangler(camera_group_shared_memory_fixture: CameraGroupSharedMemory,
                        camera_group_orchestrator_fixture: CameraGroupOrchestrator,
                        image_fixture: np.ndarray,
                        frame_metadata_fixture: np.ndarray,
                        frame_wrangler_fixture: FrameWrangler):
    og_shm_manager, recreated_shm_manager = camera_group_shared_memory_fixture
    exit_event = multiprocessing.Event()
    camera_configs = og_shm_manager.camera_configs
    frame_wrangler_fixture.start()
    [triggers.set_ready() for triggers in camera_group_orchestrator_fixture.camera_triggers.values()]
    number_of_frames_to_test = 4
    for frame_number in range(number_of_frames_to_test):
        for camera_id, config in camera_configs.items():
            cam_shm = og_shm_manager.get_camera_shared_memory(camera_id)
            cam_triggers = camera_group_orchestrator_fixture.camera_triggers[camera_id]
            cam_shm.put_new_frame(image=image_fixture, metadata=frame_metadata_fixture)
            cam_triggers.set_new_frame_available()
            assert cam_triggers.new_frame_available

        assert camera_group_orchestrator_fixture.new_frames_available
        camera_group_orchestrator_fixture.set_frames_copied()
        camera_group_orchestrator_fixture._await_mf_copied_from_shm()
        assert not camera_group_orchestrator_fixture.new_frames_available

    frame_wrangler_fixture.close()
    assert not frame_wrangler_fixture.is_alive()
