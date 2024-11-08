import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional

logger = logging.getLogger(__name__)


class ControllerTaskManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor()
        self._connect_to_cameras_task: Optional[Future] = None
        self._detect_available_cameras_task: Optional[Future] = None
        self._update_camera_configs_task: Optional[Future] = None
        self._close_cameras_task: Optional[Future] = None

    @property
    async def connect_to_cameras_task(self) -> Future:
        return self._connect_to_cameras_task

    @connect_to_cameras_task.setter
    def connect_to_cameras_task(self, value: Future) -> None:
        if self._connect_to_cameras_task is None or self._connect_to_cameras_task.done():
            self._connect_to_cameras_task = value
            return
        else:
            logger.warning("Camera connection task already running! Ignoring request...")

    @property
    async def update_camera_configs_task(self) -> Future:
        return self._update_camera_configs_task

    @update_camera_configs_task.setter
    def update_camera_configs_task(self, value: Future) -> None:
        if self._update_camera_configs_task is None or self._update_camera_configs_task.done():
            self._update_camera_configs_task = value
            return
        else:
            logger.warning("Camera connection task already running! Ignoring request...")

    @property
    def detect_available_cameras_task(self) -> Future:
        return self._detect_available_cameras_task

    @detect_available_cameras_task.setter
    def detect_available_cameras_task(self, value: Future) -> None:
        if self._detect_available_cameras_task is None or self._detect_available_cameras_task.done():
            self._detect_available_cameras_task = value
            return
        else:
            logger.warning("Camera detection task already running! Ignoring request...")

    @property
    def close_cameras_task(self) -> Future:
        return self._close_cameras_task

    @close_cameras_task.setter
    def close_cameras_task(self, value: Future) -> None:
        if self._close_cameras_task is None or self._close_cameras_task.done():
            self._close_cameras_task = value
            return
        else:
            logger.warning("Camera close task already running! Ignoring request...")
