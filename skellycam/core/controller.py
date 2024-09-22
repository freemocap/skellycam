import asyncio
import logging
import multiprocessing
from typing import Optional

from skellycam.api.app.app_state import AppState, get_app_state
from skellycam.api.app.controller_tasks import ControllerTasks
from skellycam.api.routes.websocket.ipc import get_ipc_queue, get_frame_wrangler_pipe
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

        self._app_state: AppState = get_app_state()
        self._tasks: ControllerTasks = ControllerTasks()
        self._ipc_queue = get_ipc_queue()

    @property
    def ipc_queue(self) -> multiprocessing.Queue:
        return self._ipc_queue

    async def detect_available_cameras(self):
        # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client
        logger.info(f"Detecting available cameras...")
        self._tasks.detect_available_cameras_task = asyncio.create_task(detect_available_devices(),
                                                                        name="DetectAvailableCameras")

    async def connect_to_cameras(self, camera_configs: Optional[CameraConfigs] = None):
        if camera_configs is None:
            logger.info(f"Connecting to available cameras...")
            self._tasks.connect_to_cameras_task = asyncio.create_task(
                self._create_camera_group(),
                name="ConnectToCameras")

        else:
            if self._camera_group:
                logger.debug(f"Updating CameraGroup with configs: {camera_configs}")
                self._tasks.update_camera_configs_task = asyncio.create_task(
                    self._camera_group.update_camera_configs(new_configs=camera_configs,
                                                             old_configs=self._app_state.camera_configs),
                    name="UpdateCameraConfigs")
            else:
                logger.info(f"Connecting to cameras: {camera_configs}")
                self._app_state.camera_configs = camera_configs
                self._tasks.connect_to_cameras_task = asyncio.create_task(self._create_camera_group(),
                                                                          name="ConnectToCameras")


    async def close_cameras(self):
        if self._camera_group is not None:
            logger.debug(f"Closing camera group...")
            self._tasks.close_cameras_task = asyncio.create_task(self._close_camera_group(), name="CloseCameras")
            return
        logger.warning("No camera group to close!")


    async def start_recording(self):
        logger.debug("Setting `record_frames_flag` ")
        self._app_state.record_frames_flag.value = True

    async def stop_recording(self):
        logger.debug("Setting `record_frames_flag` to False")
        self._app_state.record_frames_flag.value = False

    async def _create_camera_group(self):
        if self._app_state.camera_configs is None:
            await detect_available_devices()

        if self._camera_group:  # if `connect/` called w/o configs, reset existing connection
            await self._close_camera_group()
        self._app_state.kill_camera_group_flag.value = False
        self._app_state.record_frames_flag.value = False

        self._camera_group = CameraGroup(ipc_queue=self._ipc_queue)
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
