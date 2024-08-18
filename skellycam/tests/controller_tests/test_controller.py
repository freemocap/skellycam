from unittest.mock import AsyncMock, patch

import pytest

from skellycam.core.camera_group_manager import CameraGroupManager
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group import CameraGroup
from skellycam.core.detection.camera_device_info import AvailableDevices


@pytest.mark.asyncio
async def test_connect_with_camera_configs(controller_fixture: CameraGroupManager,
                                           camera_configs_fixture: CameraConfigs):
    with patch.object(CameraGroup, 'start', new_callable=AsyncMock) as mock_start:
        camera_ids = await controller_fixture.connect(camera_configs=camera_configs_fixture)
        assert camera_ids == controller_fixture._camera_group.camera_ids
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_connect_without_camera_configs(controller_fixture: CameraGroupManager,
                                              available_devices_fixture: AvailableDevices):
    with patch('skellycam.core.detection.detect_available_devices.detect_available_devices',
               new_callable=AsyncMock) as mock_detect:
        mock_detect.return_value = available_devices_fixture
        with patch.object(CameraGroup, 'start', new_callable=AsyncMock) as mock_start:
            camera_ids = await controller_fixture.connect()
            assert camera_ids == controller_fixture._camera_group.camera_ids
            mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_start_camera_group(controller_fixture: CameraGroupManager):
    with patch.object(CameraGroup, 'start', new_callable=AsyncMock) as mock_start:
        await controller_fixture._start_camera_group()
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_close(controller_fixture: CameraGroupManager):
    with patch.object(CameraGroup, 'close', new_callable=AsyncMock) as mock_close:
        await controller_fixture.close()
        mock_close.assert_called_once()
