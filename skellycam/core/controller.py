import logging
from typing import Optional, Tuple

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group import (
    CameraGroup,
)
from skellycam.core.detection.detect_available_devices import AvailableDevices, detect_available_devices

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()
        self._camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._camera_group = CameraGroup()

    async def detect(self) -> AvailableDevices:
        logger.info(f"Detecting cameras...")
        self._available_devices = await detect_available_devices()

        if len(self._available_devices) == 0:
            logger.warning(f"No cameras detected!")
            return self._available_devices

        self._camera_configs = {}
        for camera_id in self._available_devices.keys():
            self._camera_configs[CameraId(camera_id)] = CameraConfig(camera_id=CameraId(camera_id))
        self._camera_group.set_camera_configs(self._camera_configs)
        return self._available_devices

    async def connect_to_cameras(self,
                                 camera_configs: Optional[CameraConfigs] = None,
                                 number_of_frames: Optional[int] = None) -> Tuple[CameraConfigs, AvailableDevices]:
        logger.info(f"Connecting to available cameras...")

        if camera_configs:
            self._camera_configs = camera_configs
            self._camera_group.set_camera_configs(camera_configs)
        else:
            logger.info(f"Available cameras not set - Executing `detect` method...")
            if not await self.detect():
                raise ValueError("No cameras detected!")

        await self._start_camera_group(number_of_frames=number_of_frames)
        return self._camera_configs, self._available_devices

    async def _start_camera_group(self, number_of_frames: Optional[int] = None):
        logger.debug(f"Starting camera group with cameras: {self._camera_group.camera_ids}")
        if self._camera_configs is None or len(self._camera_configs) == 0:
            raise ValueError("No cameras available to start camera group!")
        await self._camera_group.start(number_of_frames=number_of_frames)

    async def close(self):
        logger.debug(f"Closing camera group...")
        if self._camera_group is not None:
            await self._camera_group.close()

    def start_recording(self) -> bool:
        return self._camera_group.start_recording()

    def stop_recording(self) -> bool:
        return self._camera_group.stop_recording()


CAMERA_GROUP_MANAGER = None


def create_controller() -> Controller:
    global CAMERA_GROUP_MANAGER
    if not CAMERA_GROUP_MANAGER:
        CAMERA_GROUP_MANAGER = Controller()
    return CAMERA_GROUP_MANAGER


def get_controller() -> Controller:
    global CAMERA_GROUP_MANAGER
    if not isinstance(CAMERA_GROUP_MANAGER, Controller):
        raise ValueError("Controller not created!")
    return CAMERA_GROUP_MANAGER
