import multiprocessing

from skellycam.core.cameras.trigger_camera.multi_camera_trigger_loop import multi_camera_trigger_loop
from skellycam.utilities.wait_functions import wait_10ms


def test_multi_camera_trigger_loop(
        camera_configs_fixture,
        camera_shared_memory_fixture,
):

    shm_manager, recreated_shm_manager = camera_shared_memory_fixture
    shm_names = shm_manager.shared_memory_names
    exit_event = multiprocessing.Event()
    loop_thread = multiprocessing.Process(
        target=multi_camera_trigger_loop, args=(camera_configs_fixture, shm_names, exit_event)
    )
    loop_thread.start()
    wait_10ms()
    exit_event.set()
    loop_thread.join()
    assert True
