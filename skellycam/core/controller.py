import asyncio
import logging
import multiprocessing
from typing import Optional, List

from skellycam.core.backend_state import BackendState, get_backend_state
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
        self._kill_camera_group_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self._record_frames_flag: multiprocessing.Value = multiprocessing.Value("b", False)
        self._tasks: List[asyncio.Task] = []

        self._backend_state: BackendState = get_backend_state()
        self._backend_state.record_frames_flag = self._record_frames_flag
        self._backend_state.kill_camera_group_flag = self._kill_camera_group_flag

    async def detect_available_cameras(self):
        logger.info(f"Detecting available cameras...")
        self._tasks.append(asyncio.create_task(detect_available_devices()))

    async def connect_to_cameras(self, camera_configs: Optional[CameraConfigs] = None):
        if camera_configs is None:
            logger.info(f"Connecting to available cameras...")
        else:
            self._backend_state.camera_configs = camera_configs
            logger.info(f"Connecting to cameras: {camera_configs.keys()}")

        self._tasks.append(asyncio.create_task(self._camera_group.start()))

    async def close_cameras(self):
        if self._camera_group is not None:
            logger.debug(f"Closing camera group...")
            self._tasks.append(asyncio.create_task(self._camera_group.close()))
            return
        logger.warning("No camera group to close!")

    def start_recording(self):
        logger.debug("Setting `record_frames_flag` ")
        self._record_frames_flag.value = True

    def stop_recording(self):
        logger.debug("Setting `record_frames_flag` to False")
        self._record_frames_flag.value = False

    async def _create_camera_group(self):
        if self._camera_group:
            logger.debug("Closing existing camera group...")
            self._kill_camera_group_flag.value = True
            await self._camera_group.close()

        if self._backend_state.camera_configs is None:
            await detect_available_devices()

        self._kill_camera_group_flag.value = False
        self._record_frames_flag.value = False

        self._camera_group = CameraGroup()
        await self._camera_group.start()

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
