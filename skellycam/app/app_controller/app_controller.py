import asyncio
import logging
import multiprocessing
from asyncio import Future
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable

from pydantic import BaseModel, ConfigDict, Field

from skellycam.app.app_state import AppState
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.detection.detect_available_devices import detect_available_devices

logger = logging.getLogger(__name__)


class ControllerThreadManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor()
        self._connect_to_cameras_task: Optional[Future] = None
        self._detect_available_cameras_task: Optional[Future] = None
        self._update_camera_configs_task: Optional[Future] = None

    def submit_task(self, task_name: str, task_callable: Callable, *args, **kwargs) -> Optional[Future]:
        if getattr(self, f"_{task_name}_task") is None or getattr(self, f"_{task_name}_task").done():
            future = self.executor.submit(task_callable, *args, **kwargs)
            setattr(self, f"_{task_name}_task", future)
            return future
        else:
            logger.warning(f"{task_name} task already running! Ignoring request...")
            return None


class AppController(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    app_state: AppState
    tasks: ControllerThreadManager = Field(default_factory=ControllerThreadManager)

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls(app_state=AppState.create(global_kill_flag=global_kill_flag))

    def detect_available_cameras(self):
        # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client?
        logger.info(f"Detecting available cameras...")

        self.tasks.submit_task("detect_available_cameras", self._detect_available_devices)

    def connect_to_cameras(self, camera_configs: Optional[CameraConfigs] = None):
        try:
            if camera_configs and self.app_state.camera_group:
                # if CameraGroup already exists, check if new configs require reset
                update_instructions = UpdateInstructions.from_configs(new_configs=camera_configs,
                                                                      old_configs=self.app_state.camera_group_configs)
                if not update_instructions.reset_all:
                    # Update instructions do not require reset - update existing camera group
                    logger.debug(f"Updating CameraGroup with configs: {camera_configs}")
                    self.app_state.update_camera_group(camera_configs=camera_configs,
                                                             update_instructions=update_instructions)
                    return

                # Update instructions require reset - close existing group (will be re-created below)
                logger.debug(f"Updating CameraGroup requires reset - closing existing group and reconnecting...")

            logger.info(f"Connecting to cameras....")
            self.tasks.submit_task("connect_to_cameras", self._create_camera_group, camera_configs=camera_configs)
        except Exception as e:
            logger.exception(f"Error connecting to cameras: {e}")
            raise

    def start_recording(self):
        logger.info("Starting recording...")
        self.app_state.start_recording()

    def stop_recording(self):
        logger.info("Starting recording...")
        self.app_state.stop_recording()


    def _create_camera_group(self, camera_configs: Optional[CameraConfigs]):
        try:
            if not self.app_state.available_devices and not camera_configs:
                self._detect_available_devices()
                if not self.app_state.available_devices:
                    logger.warning("No available devices detected!")
                    return

            if self.app_state.camera_group_configs is None:
                raise ValueError("No camera configurations detected!")

            if self.app_state.camera_group:  # if `connect/` called w/o configs, reset existing connection
                self.app_state.close_camera_group()

            self.app_state.create_camera_group()
            self.app_state.camera_group.start()
            logger.info("Camera group started")
        except Exception as e:
            logger.exception(f"Error creating camera group:  {e}")
            raise

    def _detect_available_devices(self):
        try:
            self.app_state.set_available_devices(detect_available_devices())
        except Exception as e:
            logger.exception(f"Error detecting available devices: {e}")
            raise

    def close(self):
        logger.info("Closing controller...")
        self.app_state.ipc_flags.global_kill_flag.value = True
        self.close_camera_group()

    def close_camera_group(self):
        logger.info("Closing camera group...")
        self.app_state.close_camera_group()



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
