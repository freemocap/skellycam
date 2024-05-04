import logging
import pprint
from typing import Coroutine, Callable, Optional

from skellycam.backend.api.http.detect import CamerasDetectedResponse
from skellycam.backend.core.cameras.camera_group import (
    CameraGroup,
)
from skellycam.backend.core.cameras.config.camera_config import CameraConfigs, CameraConfig
from skellycam.backend.core.device_detection.detect_available_cameras import DetectedCameras, detect_available_cameras

f

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ws_send_bytes: Callable[[bytes], Coroutine],
                 ) -> None:
        super().__init__()
        self._available_cameras: DetectedCameras = {}
        self._camera_configs: CameraConfigs = {}
        self._camera_group = CameraGroup(ws_send_bytes=ws_send_bytes)

    async def detect(self) -> DetectedCameras:
        logger.debug(f"Detecting available cameras...")
        detected_cameras = await detect_available_cameras()
        self._available_cameras = detected_cameras
        logger.debug(f"Detected cameras: {list(detected_cameras.keys())}")
        self._camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in self._available_cameras.keys()}
        self._camera_group.set_camera_configs(self._camera_configs)
        return detected_cameras

    async def connect(self, camera_configs: Optional[CameraConfigs] = None) -> CamerasDetectedResponse:
        logger.debug(f"Connecting to cameras...")
        if camera_configs:
            self.update_camera_configs(camera_configs)
        await self._start_camera_group()
        return CamerasDetectedResponse(detected_cameras=self._available_cameras)


    def start_recording(self, recording_folder_path: str):
        logger.debug(f"Starting recording...")
        self._camera_group.frame_wrangler.start_recording(recording_folder_path)

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._camera_group.frame_wrangler.stop_recording()

    async def _start_camera_group(self):
        if len(self._available_cameras) == 0:
            raise ValueError("No cameras available to start camera group!")
        logger.debug(f"Starting camera group...")
        await self._camera_group.start_cameras()

    def close(self):
        logger.debug(f"Stopping camera group thread...")
        self._camera_group.close()

    def update_camera_configs(self, camera_configs: CameraConfigs, strict: bool = False):
        logger.debug(f"Updating camera configs to \n{pprint.pformat(camera_configs, indent=2)}")
        self._camera_configs = camera_configs
        if self._camera_group:
            self._camera_group.update_configs(camera_configs=camera_configs,
                                              strict=strict)

    async def __aenter__(self):
        logger.debug(f"Entering Controller context manager...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug(f"Exiting Controller context manager...")
        self.close()
        return False
