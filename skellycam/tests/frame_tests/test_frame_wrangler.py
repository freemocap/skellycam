import multiprocessing

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory


@pytest.mark.run(order=-2)
def test_frame_wrangler(
        camera_configs_fixture: CameraConfigs,
        multi_camera_triggers_fixture: CameraGroupOrchestrator,
        image_fixture: np.ndarray,
        frame_metadata_fixture: np.ndarray,
):
    assert camera_configs_fixture.keys() == multi_camera_triggers_fixture.camera_triggers.keys()
    shm_manager = CameraGroupSharedMemory.create(camera_configs=camera_configs_fixture)
    exit_event = multiprocessing.Event()

    frame_wrangler = FrameWrangler(camera_configs=camera_configs_fixture,
                                   group_shm_names=shm_manager.shared_memory_names,
                                   group_orchestrator=multi_camera_triggers_fixture,
                                   exit_event=exit_event,
                                   )
    frame_wrangler.start()
    [triggers.set_ready() for triggers in multi_camera_triggers_fixture.camera_triggers.values()]
    multi_camera_triggers_fixture.fire_initial_triggers()
    [triggers.wait_for_initial_triggers_reset() for triggers in multi_camera_triggers_fixture.camera_triggers.values()]
    number_of_frames_to_test = 4
    for frame_number in range(number_of_frames_to_test):
        for camera_id, config in camera_configs_fixture.items():
            cam_shm = shm_manager.get_camera_shared_memory(camera_id)
            cam_triggers = multi_camera_triggers_fixture.camera_triggers[camera_id]
            cam_shm.put_new_frame(image=image_fixture, metadata=frame_metadata_fixture)
            cam_triggers.set_frame_retrieved()
            assert cam_triggers.new_frame_available

        assert multi_camera_triggers_fixture.new_frames_available
        multi_camera_triggers_fixture.set_frames_copied()
        multi_camera_triggers_fixture._await_frames_copied()
        assert not multi_camera_triggers_fixture.new_frames_available

    frame_wrangler.close()
    shm_manager.close_and_unlink()
