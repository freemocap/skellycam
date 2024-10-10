import pytest

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.app_controller import AppController


@pytest.mark.skip(reason="This test is not implemented yet.")
@pytest.mark.asyncio
async def test_camera_connect(controller_fixture: AppController,
                              camera_configs_fixture: CameraConfigs,
                              number_of_frames: int = 3):
    await controller_fixture.connect(camera_configs=camera_configs_fixture,
                                     number_of_frames=number_of_frames)
    camera_group = controller_fixture._camera_group

    assert camera_group.camera_ids is not None
    assert camera_group.camera_ids == list(camera_configs_fixture.keys())
    assert camera_group._camera_group_process is None
