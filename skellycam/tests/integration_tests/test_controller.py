import pytest

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.controller.controller import Controller


@pytest.fixture
def controller_fixture() -> Controller:
    return Controller()


@pytest.mark.asyncio
@pytest.mark.skip
async def test_camera_connect(controller_fixture: Controller,
                              camera_configs_fixture: CameraConfigs,
                              number_of_frames: int = 3):
    await controller_fixture.connect(camera_configs=camera_configs_fixture,
                                     number_of_frames=number_of_frames)
    await controller_fixture.close()
