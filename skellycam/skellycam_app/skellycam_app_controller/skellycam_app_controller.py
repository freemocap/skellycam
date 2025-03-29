import logging
import multiprocessing
from asyncio import Future
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable

from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.recorders.start_recording_request import StartRecordingRequest
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, create_skellycam_app
from skellycam.system.device_detection.detect_available_cameras import get_available_cameras, CameraDetectionStrategies

logger = logging.getLogger(__name__)

#
# class ControllerThreadManager:
#     def __init__(self):
#         self.executor = ThreadPoolExecutor()
#         self._connect_to_cameras_task: Optional[Future] = None
#         self._detect_available_cameras_task: Optional[Future] = None
#         self._update_camera_configs_task: Optional[Future] = None
#
#     def submit_task(self, task_name: str, task_callable: Callable, *args, **kwargs):
#         if getattr(self, f"_{task_name}_task") is None or getattr(self, f"_{task_name}_task").done():
#             future = self.executor.submit(task_callable, *args, **kwargs)
#             setattr(self, f"_{task_name}_task", future)
#             logger.debug(f"Submitted `{task_name}` task: " + str(future))
#         else:
#             logger.warning(f"{task_name} task already running! Ignoring request...")
#
#
# class SkellycamAppController(BaseModel):
#     model_config = ConfigDict(arbitrary_types_allowed=True)
#     app_state: SkellycamAppState
#     tasks: ControllerThreadManager = Field(default_factory=ControllerThreadManager)
#
#     @classmethod
#     def create(cls,
#                skellycam_app_state: SkellycamAppState):
#         return cls(app_state=skellycam_app_state)
#
#     def detect_available_cameras(self):
#         # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client?
#         logger.info(f"Detecting available cameras...")
#
#         self.tasks.submit_task("detect_available_cameras", self._detect_available_cameras)
#
#     def connect_to_cameras(self, camera_configs:CameraConfigs):
#         try:
#             logger.info(f"Connecting to cameras....")
#             self.tasks.submit_task("connect_to_cameras", self._create_camera_group)
#         except Exception as e:
#             logger.exception(f"Error connecting to cameras: {e}")
#             raise
#
#     def start_recording(self, request: StartRecordingRequest):
#         logger.info("Starting recording...")
#         self.app_state.start_recording(request)
#
#     def stop_recording(self):
#         logger.info("Starting recording...")
#         self.app_state.stop_recording()
#
#     def create_camera_group(self, camera_configs: CameraConfigs):
#         try:
#             self.app_state.create_camera_group(camera_configs=camera_configs)
#             self.app_state.camera_group.start()
#             logger.info("Camera group started")
#         except Exception as e:
#             logger.exception(f"Error creating camera group:  {e}")
#             raise
#
#     def _detect_available_cameras(self, strategy: CameraDetectionStrategies):
#         try:
#             self.app_state.set_available_cameras(get_available_cameras(strategy=strategy))
#         except Exception as e:
#             logger.exception(f"Error detecting available devices: {e}")
#             raise
#
#     def close_camera_group(self):
#         logger.info("Closing camera group...")
#         self.app_state.close_camera_group()
#
#     def shutdown(self):
#         logger.info("Closing controller...")
#         self.app_state.ipc_flags.global_kill_flag.value = True
#         self.close_camera_group()
#
#
# SKELLYCAM_APP_CONTROLLER = None
#
#
# def create_skellycam_app_controller(global_kill_flag: multiprocessing.Value
#                                     ) -> SkellycamAppController:
#     global SKELLYCAM_APP_CONTROLLER
#     if not SKELLYCAM_APP_CONTROLLER:
#         SKELLYCAM_APP_CONTROLLER = SkellycamAppController.create(
#             skellycam_app_state=create_skellycam_app_state(global_kill_flag=global_kill_flag))
#
#
#     return SKELLYCAM_APP_CONTROLLER
#
#
# def get_skellycam_app_controller() -> SkellycamAppController:
#     global SKELLYCAM_APP_CONTROLLER
#     if not isinstance(SKELLYCAM_APP_CONTROLLER, SkellycamAppController):
#         raise ValueError("AppController not created!")
#     return SKELLYCAM_APP_CONTROLLER
