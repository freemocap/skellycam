import logging
import pprint
from typing import Optional, Coroutine, Callable

from skellycam.backend.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.backend.core.camera_group.camera_group import (
    CameraGroup,
)
from skellycam.backend.core.device_detection.detect_available_cameras import detect_available_cameras, DetectedCameras

logger = logging.getLogger(__name__)
logging.getLogger(__name__).setLevel(5)


class Controller:
    def __init__(self, ws_send_bytes: Callable[[bytes], Coroutine]) -> None:
        super().__init__()
        self._ws_send_bytes = ws_send_bytes
        self._available_cameras: Optional[DetectedCameras] = None
        self._camera_configs: Optional[CameraConfigs] = None
        self._camera_group: Optional[CameraGroup] = None

    @property
    def camera_configs(self) -> CameraConfigs:
        if self._camera_configs is None:
            self._camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in
                                    list(self._available_cameras.keys())}
        return self._camera_configs

    async def detect(self):
        detected_cameras_response = await detect_available_cameras()
        self._available_cameras = detected_cameras_response.detected_cameras
        return detected_cameras_response

    async def send_latest_frames(self):
        ws_payload = self._camera_group.latest_frontend_payload.to_msgpack()
        logger.trace(f"Sending multi-frame payload to websocket server ({len(ws_payload) / 1024}kb)...")
        await self._ws_send_bytes(ws_payload)

    def start_recording(self, recording_folder_path: str):
        logger.debug(f"Starting recording...")
        self._camera_group.frame_wrangler.start_recording(recording_folder_path)

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._camera_group.frame_wrangler.stop_recording()

    async def start_camera_group(self) -> None:
        logger.debug(f"Starting camera group...")
        self._camera_group = CameraGroup(camera_configs=self.camera_configs)
        await self._camera_group.start_frame_loop()

    def close(self):
        logger.debug(f"Stopping camera group thread...")
        self._camera_group.close()

    def update_camera_configs(self, camera_configs: CameraConfigs):
        logger.debug(f"Updating camera configs to \n{pprint.pformat(camera_configs, indent=2)}")
        self._camera_configs = camera_configs
        if self._camera_group:
            self._camera_group.update_configs(camera_configs=camera_configs)

    async def __aenter__(self):
        logger.debug(f"Entering Controller context manager...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug(f"Exiting Controller context manager...")
        self.close()
        return False
