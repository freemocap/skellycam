import asyncio
import logging
from typing import Optional, List

from skellycam.api.app.app_state import AppState, get_app_state
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group import (
    CameraGroup,
)
from skellycam.core.detection.detect_available_devices import detect_available_devices

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()
        self._camera_group: Optional[CameraGroup] = None

        self._tasks: List[asyncio.Task] = []

        self._app_state: AppState = get_app_state()

    async def detect_available_cameras(self):
        logger.info(f"Detecting available cameras...")
        self._tasks.append(asyncio.create_task(detect_available_devices()))

    async def connect_to_cameras(self, camera_configs: Optional[CameraConfigs] = None):
        if camera_configs is None:
            logger.info(f"Connecting to available cameras...")
        else:
            self._app_state.camera_configs = camera_configs
            logger.info(f"Connecting to cameras: {camera_configs.keys()}")

        self._tasks.append(asyncio.create_task(self._create_camera_group()))

    async def close_cameras(self):
        if self._camera_group is not None:
            logger.debug(f"Closing camera group...")
            self._tasks.append(asyncio.create_task(self._close_camera_group()))
            return
        logger.warning("No camera group to close!")

    async def start_recording(self):
        logger.debug("Setting `record_frames_flag` ")
        self._app_state.record_frames_flag.value = True

    async def stop_recording(self):
        logger.debug("Setting `record_frames_flag` to False")
        self._app_state.record_frames_flag.value = False

    async def _create_camera_group(self):
        if self._camera_group:
            await self._close_camera_group()

        if self._app_state.camera_configs is None:
            await detect_available_devices()

        self._app_state.kill_camera_group_flag.value = False
        self._app_state.record_frames_flag.value = False

        self._camera_group = CameraGroup()
        await self._camera_group.start()

    async def _close_camera_group(self):
        logger.debug("Closing existing camera group...")
        self._app_state.kill_camera_group_flag.value = True
        await self._camera_group.close()
        self._camera_group = None


CONTROLLER = None


def create_controller() -> Controller:
    global CONTROLLER
    if not CONTROLLER:
        CONTROLLER = Controller()
    return CONTROLLER


def get_controller() -> Controller:
    global CONTROLLER
    if not isinstance(CONTROLLER, Controller):
        raise ValueError("Controller not created!")
    return CONTROLLER
