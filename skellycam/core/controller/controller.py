import logging
from typing import Coroutine, Callable, Optional

from skellycam.core import CameraId
from skellycam.core.cameras.camera_group import (
    CameraGroup,
)
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.detect_available_devices import AvailableDevices, detect_available_devices

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()
        self._camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None
        self._camera_group = CameraGroup()

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._camera_group.set_websocket_bytes_sender(ws_send_bytes)

    async def detect(self) -> AvailableDevices:
        logger.info(f"Detecting cameras...")
        self._available_devices = await detect_available_devices()
        self._camera_configs = CameraConfigs()
        for camera_id in self._available_devices.keys():
            self._camera_configs[CameraId(camera_id)] = CameraConfig(camera_id=CameraId(camera_id))
        self._camera_group.set_camera_configs(self._camera_configs)
        return self._available_devices

    async def connect(self,
                      camera_configs: Optional[CameraConfigs] = None,
                      number_of_frames: Optional[int] = None):
        logger.info(f"Connecting to available cameras...")

        if camera_configs:
            await self.update_camera_configs(camera_configs)
        if not self._camera_configs:
            logger.info(f"Available cameras not set - Executing `detect` method...")
            await self.detect()

        await self._start_camera_group(number_of_frames=number_of_frames)
        return self._camera_group.camera_ids

    def start_recording(self, recording_folder_path: str):
        logger.debug(f"Starting recording...")
        self._camera_group.frame_wrangler.start_recording(recording_folder_path)

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._camera_group.frame_wrangler.stop_recording()

    async def _start_camera_group(self, number_of_frames: Optional[int] = None):
        logger.debug(f"Starting camera group with cameras: {self._camera_group.camera_ids}")
        if len(self._available_devices) == 0:
            raise ValueError("No cameras available to start camera group!")
        await self._camera_group.start_cameras(number_of_frames=number_of_frames)

    async def close(self):
        logger.debug(f"Closing camera group...")
        await self._camera_group.close()

    async def update_camera_configs(self,
                                    camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs to {camera_configs}")
        self._camera_configs = camera_configs
        if self._camera_group:
            await self._camera_group.update_configs(camera_configs=camera_configs)
