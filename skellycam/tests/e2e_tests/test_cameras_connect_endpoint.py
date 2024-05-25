import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.controller.controller import Controller


@pytest.fixture
def controller_fixture() -> Controller:
    return Controller()


@pytest.mark.asyncio
async def test_camera_connect(controller_fixture: Controller,
                              camera_configs_fixture: CameraConfigs,
                              number_of_frames: int = 3):
    from skellycam.system.utilities.wait_functions import wait_1s

    await controller_fixture.connect(camera_configs=camera_configs_fixture,
                                     number_of_frames=number_of_frames)
    cg = controller_fixture._camera_group
    c_ids = list(camera_configs_fixture.keys())
    shm_names = cg._camera_shm_manager.shared_memory_names
    assert cg.camera_ids == c_ids

    assert list(cg._multicam_triggers.single_camera_triggers.keys()) == c_ids
    assert cg._multi_camera_process is not None
    assert cg._camera_shm_manager.camera_configs == camera_configs_fixture
    assert cg._frame_wrangler._camera_configs == camera_configs_fixture
    assert cg._frame_wrangler._shared_memory_names == shm_names
    assert cg._frame_wrangler.payloads_received is not None

    max_wait = 3
    for i in range(max_wait):
        if cg._frame_wrangler.payloads_received == number_of_frames:
            break
        wait_1s()
    assert cg._frame_wrangler.payloads_received == number_of_frames

    await controller_fixture.close()
