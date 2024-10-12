import asyncio
import logging
import multiprocessing
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from skellycam.app.app_controller.controller_tasks import ControllerTasks
from skellycam.app.app_state import create_app_state, AppState
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.detection.detect_available_devices import detect_available_devices

logger = logging.getLogger(__name__)


class AppController(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    app_state: AppState
    tasks: ControllerTasks = Field(default_factory=ControllerTasks)

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls( app_state=create_app_state(global_kill_flag=global_kill_flag))

    async def detect_available_cameras(self):
        # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client?
        logger.info(f"Detecting available cameras...")

        self.tasks.detect_available_cameras_task = asyncio.create_task(detect_available_devices(),
                                                                        name="DetectAvailableCameras")

    async def connect_to_cameras(self, camera_configs: Optional[CameraConfigs]=None):
        try:
            if camera_configs and self.app_state.camera_group:
                # if CameraGroup already exists, check if new configs require reset
                update_instructions = UpdateInstructions.from_configs(new_configs=camera_configs,
                                                                      old_configs=self.app_state.camera_group_configs)
                if not update_instructions.reset_all:
                    # Update instructions do not require reset - update existing camera group
                    logger.debug(f"Updating CameraGroup with configs: {camera_configs}")
                    await self.app_state.update_camera_group(camera_configs=camera_configs,
                                                              update_instructions=update_instructions)
                    return

                # Update instructions require reset - close existing group (will be re-created below)
                logger.debug(f"Updating CameraGroup requires reset - closing existing group and reconnecting...")

            logger.info(f"Connecting to cameras....")
            self.tasks.connect_to_cameras_task = asyncio.create_task(
                self._create_camera_group(camera_configs=self.app_state.camera_group_configs),
                name="ConnectToCameras")
        except Exception as e:
            logger.exception(f"Error connecting to cameras: {e}")
            raise

    async def _create_camera_group(self, camera_configs: CameraConfigs):
        try:
            if self.app_state.camera_group_configs is None:
                await detect_available_devices()

            if self.app_state.camera_group_configs is None:
                raise ValueError("No camera configurations detected!")

            if self.app_state.camera_group:  # if `connect/` called w/o configs, reset existing connection
                await self.app_state.close_camera_group()

            self.app_state.create_camera_group()
            await self.app_state.camera_group.start()
            logger.info("Camera group started")
        except Exception as e:
            logger.exception(f"Error creating camera group:  {e}")
            raise

    async def close(self):
        logger.info("Closing controller...")
        self.app_state.ipc_flags.global_kill_flag.value = True
        await self.close_camera_group()

    async def close_camera_group(self):
        await self.app_state.close_camera_group()
APP_CONTROLLER = None


def create_app_controller(global_kill_flag: multiprocessing.Value) -> AppController:
    global APP_CONTROLLER
    if not APP_CONTROLLER:
        APP_CONTROLLER = AppController.create(global_kill_flag=global_kill_flag)
    return APP_CONTROLLER


def get_app_controller() -> AppController:
    global APP_CONTROLLER
    if not isinstance(APP_CONTROLLER, AppController):
        raise ValueError("AppController not created!")
    return APP_CONTROLLER
