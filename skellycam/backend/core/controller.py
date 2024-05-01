import asyncio
import logging
import pprint
from typing import Optional

from starlette.websockets import WebSocket

from skellycam.backend.core.camera.config.camera_config import CameraConfigs, DEFAULT_CAMERA_CONFIGS, CameraConfig
from skellycam.backend.core.camera_group.camera_group import (
    CameraGroup,
)
from skellycam.backend.core.device_detection.detect_available_cameras import detect_available_cameras, DetectedCameras
from skellycam.backend.core.frames.frame_wrangler import (
    FrameWrangler,
)
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)
logging.getLogger(__name__).setLevel(5)

CONTROLLER = None

def get_or_create_controller():
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER

async def reset_controller():
    global CONTROLLER
    if CONTROLLER is not None:
        await CONTROLLER.close()
        CONTROLLER = None
    return get_or_create_controller()

class Controller:
    def __init__(self) -> None:
        super().__init__()
        self._available_cameras: Optional[DetectedCameras] = None
        self._camera_configs: Optional[CameraConfigs] = None
        self._camera_group: Optional[CameraGroup] = None


    @property
    def connected(self) -> bool:
        return self._camera_group.any_capturing if self._camera_group else False

    @property
    def camera_configs(self) -> CameraConfigs:
        if self._camera_configs is None and self._available_cameras is None:
            self._camera_configs = DEFAULT_CAMERA_CONFIGS
        elif self._camera_configs is None:
            self._camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in
                                    list(self._available_cameras.keys())}
        return self._camera_configs


    async def detect(self):
        detected_cameras_response = await detect_available_cameras()
        self._available_cameras = detected_cameras_response.detected_cameras
        return detected_cameras_response

    def show_camera_windows(self):
        self._camera_group.frame_wrangler.start_camera_viewer()

    def start_recording(self, recording_folder_path: str):
        logger.debug(f"Starting recording...")
        self._camera_group.frame_wrangler.start_recording(recording_folder_path)

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._camera_group.frame_wrangler.stop_recording()

    async def start_camera_loop(self, websocket: WebSocket):
        logger.debug(f"Starting camera group...")
        self._camera_group = CameraGroup(camera_configs=self.camera_configs )
        await self._camera_group.start_frame_loop()

    def close(self):
        logger.debug(f"Stopping camera group thread...")
        self._camera_group.close()

    def update_camera_configs(self, camera_configs: CameraConfigs):
        logger.debug(f"Updating camera configs to \n{pprint.pformat(camera_configs, indent=2)}")
        self._camera_configs = camera_configs
        if self._camera_group:
            self._camera_group.update_configs(camera_configs=camera_configs)

    # def get_latest_frames(self) -> MultiFramePayload:
    #     return self._camera_group.frame_wrangler.latest_frontend_payload
