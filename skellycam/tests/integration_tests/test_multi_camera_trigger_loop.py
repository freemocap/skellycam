import multiprocessing
import time

from skellycam.core.cameras.trigger_camera.multi_camera_trigger_loop import multi_camera_trigger_loop


def test_multi_camera_trigger_loop(camera_configs_fixture,
                                   camera_shared_memory_fixture,
                                   ):
    from skellycam.system.utilities.wait_functions import wait_1s

    shm_manager, recreated_shm_manager = camera_shared_memory_fixture
    shm_names = shm_manager.shared_memory_names
    lock = shm_manager.lock
    exit_event = multiprocessing.Event()
    loop_thread = multiprocessing.Process(target=multi_camera_trigger_loop,
                                          args=(camera_configs_fixture,
                                                shm_names,
                                                lock,
                                                exit_event
                                                )
                                          )
    loop_thread.start()
    wait_1s()
    exit_event.set()
    loop_thread.join()
    assert True

