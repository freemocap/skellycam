import multiprocessing
import time
from typing import Tuple

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.frame_wrangler import FrameListenerProcess
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager
from skellycam.system.utilities.wait_functions import wait_1s, wait_10ms


class TestFrameListenerProcess:
    @pytest.fixture
    def setup(self,
              camera_shared_memory_fixture: Tuple[CameraSharedMemoryManager, CameraSharedMemoryManager]):
        shm_lock = multiprocessing.Lock()
        shm_manager, recreated_shm_manager = camera_shared_memory_fixture
        recreated_shm_manager.close()
        camera_configs = shm_manager.camera_configs
        multicam_triggers = MultiCameraTriggerOrchestrator.from_camera_configs(camera_configs=camera_configs)
        exit_event = multiprocessing.Event()

        flp = FrameListenerProcess(
            camera_configs=camera_configs,
            shm_lock=shm_lock,
            shared_memory_names=shm_manager.shared_memory_names,
            multicam_triggers=multicam_triggers,
            exit_event=exit_event
        )

        return {
            'camera_configs': camera_configs,
            'shm_lock': shm_lock,
            'shm_manager': shm_manager,
            'multicam_triggers': multicam_triggers,
            'flp': flp,
            'exit_event': exit_event
        }

    def test_initialization(self, setup):
        flp = setup['flp']

        assert flp._camera_configs == setup['camera_configs']
        assert flp._shm_lock == setup['shm_lock']
        assert flp._shared_memory_names == setup['shm_manager'].shared_memory_names
        assert flp._multi_camera_triggers == setup['multicam_triggers']
        assert flp._exit_event == setup['exit_event']
        assert flp._payloads_received.value == 0

    def test_start_and_exit(self, setup: dict):
        flp = setup['flp']
        flp.start()
        assert flp.is_alive()
        setup['exit_event'].set()
        flp.join()
        assert not flp.is_alive()
        assert flp.payloads_received == 0

    def test_handle_payload(self, setup: dict):
        flp = setup['flp']
        mfp = self._create_test_multiframe_payload(camera_configs=setup['camera_configs'])
        flp._handle_payload(payload=mfp)
        assert flp.payloads_received == 1

    def test_listen_for_frames(self, setup: dict):
        flp = setup['flp']
        flp.start()
        wait_1s()
        shm_manager = setup['shm_manager']
        assert flp.payloads_received == 0
        mfp = self._create_test_multiframe_payload(camera_configs=setup['camera_configs'])
        for camera_id, frame in mfp.frames.items():
            cam_shm = shm_manager.get_camera_shared_memory(camera_id)
            cam_triggers = setup['multicam_triggers'].single_camera_triggers[camera_id]
            image  = frame.image
            unhydrated_frame = frame
            unhydrated_frame.image_data = None
            assert not unhydrated_frame.hydrated
            cam_shm.put_new_frame(image=image,
                                  frame=unhydrated_frame)
            cam_triggers.set_frame_retrieved()
        wait_10ms()
        setup['exit_event'].set()
        flp.join()
        assert flp.payloads_received == 1

    def _create_test_multiframe_payload(self, camera_configs: CameraConfigs) -> MultiFramePayload:
        mfp = MultiFramePayload.create(camera_ids=camera_configs.keys())
        for camera_id, camera_config in camera_configs.items():
            image_shape = camera_config.image_shape
            frame = FramePayload.create_initial_frame(camera_id=camera_id,
                                                      image_shape=image_shape)
            frame.timestamp_ns = time.perf_counter_ns()
            frame.image = np.random.randint(0, 255, image_shape, dtype=np.uint8)
            mfp.add_frame(frame)
        assert mfp.full
        return mfp