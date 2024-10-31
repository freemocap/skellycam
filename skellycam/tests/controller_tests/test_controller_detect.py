from unittest.mock import patch, AsyncMock

import pytest

from skellycam.app.app_controller.app_controller import AppController
from skellycam.system.device_detection.camera_device_info import AvailableDevices


@pytest.mark.skip(reason="This test is not implemented yet.")
@pytest.mark.asyncio
async def test_detect_with_cameras(controller_fixture: AppController,
                                   available_devices_fixture: AvailableDevices):
    with patch('skellycam.core.detection.detect_available_devices.detect_available_devices',
               new_callable=AsyncMock) as mock_detect:
        mock_detect.return_value = available_devices_fixture
        available_devices = await controller_fixture.detect_available_cameras()
        assert controller_fixture._camera_configs.keys() == available_devices.keys()
