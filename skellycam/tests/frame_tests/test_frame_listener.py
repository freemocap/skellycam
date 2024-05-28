import multiprocessing
import time
from typing import Tuple, Dict

import numpy as np
import pytest

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group import CameraGroupOrchestrator
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.frame_wrangler import FrameListenerProcess
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_1ms


@pytest.fixture
def flp_setup(camera_shared_memory_fixture: Tuple[CameraGroupSharedMemory, CameraGroupSharedMemory],
              multi_frame_payload_fixture: MultiFramePayload, ) -> Dict[str, any]:
    shm_manager, recreated_shm_manager = camera_shared_memory_fixture
    camera_configs = shm_manager.camera_configs
    multicam_triggers = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs)
    [cam_triggers.set_ready() for cam_triggers in multicam_triggers.camera_triggers.values()]

    exit_event = multiprocessing.Event()

    flp = FrameListenerProcess(
        camera_configs=camera_configs,
        group_shm_names=shm_manager.shared_memory_names,
        multicam_triggers=multicam_triggers,
        exit_event=exit_event,
    )
    return {
        "flp": flp,
        "mfp": multi_frame_payload_fixture,
        "camera_configs": camera_configs,
        "shm_manager": shm_manager,
        "multicam_triggers": multicam_triggers,
        "exit_event": exit_event,
    }


def test_initialization(flp_setup: Dict[str, any]):
    flp = flp_setup["flp"]
    assert flp._exit_event == flp_setup["exit_event"]
    assert flp._payloads_received.value == 0


def test_start_and_exit(flp_setup: Dict[str, any]):
    flp = flp_setup["flp"]
    flp.start_process()
    assert flp.is_alive()
    flp_setup["exit_event"].set()
    flp.join()
    assert not flp.is_alive()
    assert flp.payloads_received == 0


def test_listen_for_frames(flp_setup: Dict[str, any]):
    flp = flp_setup["flp"]
    mfp: MultiFramePayload = flp_setup["mfp"]
    multicam_triggers: CameraGroupOrchestrator = flp_setup["multicam_triggers"]
    shm_manager: CameraGroupSharedMemory = flp_setup["shm_manager"]

    flp.start_process()
    wait_1ms()
    assert flp.payloads_received == 0
    for camera_id, frame in mfp.frames.items():
        cam_shm = shm_manager.get_camera_shared_memory(camera_id)
        cam_triggers = multicam_triggers.camera_triggers[camera_id]
        image = frame.image
        metadata = frame.metadata
        cam_shm.put_new_frame(image=image, metadata=metadata)
        cam_triggers.new_frame_available_trigger.set()
    multicam_triggers._await_frames_copied()
    assert flp.payloads_received == 1
    flp_setup["exit_event"].set()
    flp.join()


def create_test_multiframe_payload(camera_configs: CameraConfigs) -> MultiFramePayload:
    mfp = MultiFramePayload.create_initial(camera_ids=list(camera_configs.keys()))
    for camera_id, camera_config in camera_configs.items():
        image_shape = camera_config.image_shape
        frame = FramePayload.create_initial_frame(camera_id=camera_id, image_shape=image_shape)
        frame.timestamp_ns = time.perf_counter_ns()
        frame.image = np.random.randint(0, 255, image_shape, dtype=np.uint8)
        mfp.add_frame(frame)
    assert mfp.full
    return mfp
