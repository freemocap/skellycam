import asyncio
import logging
import multiprocessing
from typing import Optional

from skellycam.app.app_controller.controller_tasks import ControllerTasks
from skellycam.app.app_state import create_app_state, AppState
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.detection.detect_available_devices import detect_available_devices

logger = logging.getLogger(__name__)


class AppController:
    def __init__(self,
                 global_kill_flag: multiprocessing.Value) -> None:
        super().__init__()
        self._app_state: AppState = create_app_state(global_kill_flag=global_kill_flag)
        self._tasks: ControllerTasks = ControllerTasks()

    async def detect_available_cameras(self):
        # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client?
        logger.info(f"Detecting available cameras...")
        self._tasks.detect_available_cameras_task = asyncio.create_task(detect_available_devices(),
                                                                        name="DetectAvailableCameras")

    async def connect_to_cameras(self, camera_configs: Optional[CameraConfigs] = None):

        if camera_configs and self._app_state.camera_group:
            # CameraGroup exists and user has provided new configs
            update_instructions = UpdateInstructions.from_configs(new_configs=camera_configs,
                                                                  old_configs=self._app_state.connected_camera_configs)
            if not update_instructions.reset_all:
                # Update instructions do not require reset - update existing camera group
                logger.debug(f"Updating CameraGroup with configs: {camera_configs}")
                await self._app_state.update_camera_group(camera_configs=camera_configs,
                                                          update_instructions=update_instructions)
                return
            # Update instructions require reset - close existing group (will be re-created below)
            logger.debug(f"Updating CameraGroup requires reset - closing existing group...")
            await self._close_camera_group()

        logger.info(f"Connecting to cameras....")
        # C
        self._tasks.connect_to_cameras_task = asyncio.create_task(
            self._create_camera_group(camera_configs=camera_configs),
            name="ConnectToCameras")

    async def close(self):
        logger.info("Closing controller...")
        await self.close_cameras()

    async def close_cameras(self):
        if self._camera_group is not None:
            logger.debug(f"Closing camera group...")
            # self._tasks.close_cameras_task = asyncio.create_task(self._close_camera_group(), name="CloseCameras")
            await self._close_camera_group()
            return
        logger.warning("No camera group to close!")

    async def _create_camera_group(self, camera_configs: CameraConfigs):
        if self._app_state.connected_camera_configs is None:
            await detect_available_devices()

        if self._app_state.connected_camera_configs is None:
            raise ValueError("No camera configurations detected!")

        self._app_state.create_camera_group_shm()

        if self._camera_group:  # if `connect/` called w/o configs, reset existing connection
            await self._app_state.close_camera_group()

        self._app_state.create_camera_group(camera_configs=camera_configs)
        await self._app_state.camera_group.start()
        logger.success("Camera group started successfully")


APP_CONTROLLER = None


def create_app_controller(global_kill_flag: multiprocessing.Value) -> AppController:
    global APP_CONTROLLER
    if not APP_CONTROLLER:
        APP_CONTROLLER = AppController(global_kill_flag=global_kill_flag)
    return APP_CONTROLLER


def get_app_controller() -> AppController:
    global APP_CONTROLLER
    if not isinstance(APP_CONTROLLER, AppController):
        raise ValueError("AppController not created!")
    return APP_CONTROLLER
