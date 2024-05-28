import multiprocessing

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group import CameraGroupOrchestrator
from skellycam.core.cameras.group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_10ms


def test_multi_camera_trigger_loop(
        camera_configs_fixture: CameraConfigs,
        camera_shared_memory_fixture: CameraGroupSharedMemory,
        multi_camera_triggers_fixture: CameraGroupOrchestrator,
):
    shm_manager, recreated_shm_manager = camera_shared_memory_fixture
    shm_names = shm_manager.shared_memory_names
    exit_event = multiprocessing.Event()
    [multi_camera_triggers_fixture.camera_triggers[camera_id].camera_ready_event.set() for camera_id in
     camera_configs_fixture.keys()]
    loop_thread = multiprocessing.Process(
        target=camera_group_trigger_loop, args=(camera_configs_fixture,
                                                multi_camera_triggers_fixture,
                                                shm_names,
                                                exit_event,
                                                None,
                                                )
    )
    loop_thread.start()
    wait_10ms()
    exit_event.set()
    loop_thread.join()
    assert True
