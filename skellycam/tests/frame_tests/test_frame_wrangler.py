import multiprocessing

import numpy as np

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group import CameraGroupOrchestrator
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory


def test_frame_wrangler(
        camera_configs_fixture: CameraConfigs,
        multi_camera_triggers_fixture: CameraGroupOrchestrator,
        image_fixture: np.ndarray,
        frame_metadata_fixture: np.ndarray,
):
    assert camera_configs_fixture.keys() == multi_camera_triggers_fixture.camera_triggers.keys()
    shm_manager = CameraGroupSharedMemory.create(camera_configs=camera_configs_fixture)
    exit_event = multiprocessing.Event()

    frame_wrangler = FrameWrangler(exit_event=exit_event)
    frame_wrangler.set_camera_info(
        camera_configs=camera_configs_fixture,
        shared_memory_names=shm_manager.shared_memory_names,
        multicam_triggers=multi_camera_triggers_fixture,
    )
    frame_wrangler.start_frame_listener()
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
