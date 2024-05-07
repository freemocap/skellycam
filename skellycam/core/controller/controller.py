import logging
import pprint
from typing import Coroutine, Callable, Optional

from skellycam.core.cameras.camera_group import (
    CameraGroup,
)
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.detection.detect_available_cameras import DetectedCameras, detect_available_cameras

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()
        self._camera_configs: Optional[CameraConfigs] = None
        self._available_cameras: Optional[DetectedCameras] = None
        self._camera_group = CameraGroup()

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._camera_group.set_websocket_bytes_sender(ws_send_bytes)

    async def detect(self) -> DetectedCameras:
        logger.info(f"Detecting cameras...")
        self._available_cameras = await detect_available_cameras()
        self._camera_configs = CameraConfigs.from_dict({camera_id: CameraConfig(camera_id=CameraId(camera_id))
                                                        for camera_id in self._available_cameras.keys()})
        self._camera_group.set_camera_configs(self._camera_configs)
        return self._available_cameras

    async def connect(self,
                      camera_configs: Optional[CameraConfigs] = None,
                      number_of_frames: Optional[int] = None):
        logger.info(f"Connecting to available cameras...")

        if camera_configs:
            await self.update_camera_configs(camera_configs)
        if not self._available_cameras:
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
        if len(self._available_cameras) == 0:
            raise ValueError("No cameras available to start camera group!")
        await self._camera_group.start_cameras(number_of_frames=number_of_frames)

    async def close(self):
        logger.debug(f"Closing camera group...")
        await self._camera_group.close()

    async def update_camera_configs(self,
                                    camera_configs: CameraConfigs,
                                    strict: bool = False):
        logger.info(f"Updating camera configs to \n{pprint.pformat(camera_configs, indent=2)}")
        self._target_camera_configs = camera_configs
        if self._camera_group:
            await self._camera_group.update_configs(camera_configs=camera_configs,
                                                    strict=strict)
