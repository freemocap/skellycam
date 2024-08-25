import asyncio
import logging
import multiprocessing
from typing import Optional

from skellycam.api.app.app_state import get_app_state, AppState
from skellycam.api.routes.websocket.ipc import get_ipc_queue, get_frame_wrangler_pipe
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group import (
    CameraGroup,
)
from skellycam.core.detection.detect_available_devices import detect_available_devices

logger = logging.getLogger(__name__)


class ControllerTasks:
    def __init__(self):
        self._connect_to_cameras_task: Optional[asyncio.Task] = None
        self._detect_available_cameras_task: Optional[asyncio.Task] = None
        self._close_cameras_task: Optional[asyncio.Task] = None

    @property
    async def connect_to_cameras_task(self) -> Optional[asyncio.Task]:
        return self._connect_to_cameras_task

    @connect_to_cameras_task.setter
    def connect_to_cameras_task(self, value: Optional[asyncio.Task]) -> None:
        if self._connect_to_cameras_task is not None:
            if self._connect_to_cameras_task.done():
                self._connect_to_cameras_task = value
                return
        else:
            logger.warning("Camera connection task already running! Ignoring request...")

    @property
    def detect_available_cameras_task(self) -> Optional[asyncio.Task]:
        return self._detect_available_cameras_task

    @detect_available_cameras_task.setter
    def detect_available_cameras_task(self, value: Optional[asyncio.Task]) -> None:
        if self._detect_available_cameras_task is not None:
            if self._detect_available_cameras_task.done():
                self._detect_available_cameras_task = value
                return
        else:
            logger.warning("Camera detection task already running! Ignoring request...")

    @property
    def close_cameras_task(self) -> Optional[asyncio.Task]:
        return self._close_cameras_task

    @close_cameras_task.setter
    def close_cameras_task(self, value: Optional[asyncio.Task]) -> None:
        if self._close_cameras_task is not None:
            if self._close_cameras_task.done():
                self._close_cameras_task = value
                return
        else:
            logger.warning("Camera close task already running! Ignoring request...")

class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()
        self._camera_group: Optional[CameraGroup] = None

        self._tasks: ControllerTasks = ControllerTasks()

        self._app_state: AppState = get_app_state()
        self._ipc_queue = get_ipc_queue()
        self._frame_wrangler_pipe = get_frame_wrangler_pipe()

    @property
    def ipc_queue(self) -> multiprocessing.Queue:
        return self._ipc_queue


    async def detect_available_cameras(self):
        logger.info(f"Detecting available cameras...")
        self._tasks.detect_available_cameras_task = asyncio.create_task(detect_available_devices())

    async def connect_to_cameras(self, camera_configs: Optional[CameraConfigs] = None):
        if camera_configs is None:
            logger.info(f"Connecting to available cameras...")
        else:
            logger.info(f"Connecting to cameras: {camera_configs.keys()}")

        self._tasks.connect_to_cameras_task = asyncio.create_task(self._create_camera_group(camera_configs))

    async def close_cameras(self):
        if self._camera_group is not None:
            logger.debug(f"Closing camera group...")
            self._tasks.close_cameras_task = asyncio.create_task(self._close_camera_group())
            return
        logger.warning("No camera group to close!")

    async def start_recording(self):
        logger.debug("Setting `record_frames_flag` ")
        self._app_state.record_frames_flag.value = True

    async def stop_recording(self):
        logger.debug("Setting `record_frames_flag` to False")
        self._app_state.record_frames_flag.value = False

    async def _create_camera_group(self, camera_configs: Optional[CameraConfigs] = None):
        if self._camera_group:
            await self._close_camera_group()

        if camera_configs:
            self._app_state.camera_configs = camera_configs

        if self._app_state.camera_configs is None:
            await detect_available_devices()

        self._app_state.kill_camera_group_flag.value = False
        self._app_state.record_frames_flag.value = False

        self._camera_group = CameraGroup(ipc_queue=self._ipc_queue,
                                         frontend_pipe=self._frame_wrangler_pipe, )
        await self._camera_group.start()
        logger.success("Camera group started successfully")

    async def _close_camera_group(self):
        logger.debug("Closing existing camera group...")
        self._app_state.kill_camera_group_flag.value = True
        await self._camera_group.close()
        self._camera_group = None
        logger.success("Camera group closed successfully")


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
