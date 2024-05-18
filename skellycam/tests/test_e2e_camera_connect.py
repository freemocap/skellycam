import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.controller.controller import Controller

@pytest.mark.asyncio
async def test_e2e_camera_connect(controller_fixture:Controller,
                         camera_configs_fixture:CameraConfigs,
                         number_of_frames:int= 3):
    controller_fixture._camera_configs = camera_configs_fixture
    controller_fixture._camera_group.set_camera_configs(camera_configs_fixture)
    await controller_fixture.close()
    del controller_fixture
