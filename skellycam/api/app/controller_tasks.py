import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ControllerTasks:
    def __init__(self):
        self._connect_to_cameras_task: Optional[asyncio.Task] = None
        self._detect_available_cameras_task: Optional[asyncio.Task] = None
        self._update_camera_configs_task: Optional[asyncio.Task] = None
        self._close_cameras_task: Optional[asyncio.Task] = None

    @property
    async def connect_to_cameras_task(self) -> asyncio.Task:
        return self._connect_to_cameras_task

    @connect_to_cameras_task.setter
    def connect_to_cameras_task(self, value: asyncio.Task) -> None:
        if self._connect_to_cameras_task is None or self._connect_to_cameras_task.done():
            self._connect_to_cameras_task = value
            return
        else:
            logger.warning("Camera connection task already running! Ignoring request...")

    @property
    async def update_camera_configs_task(self) -> asyncio.Task:
        return self._update_camera_configs_task

    @update_camera_configs_task.setter
    def update_camera_configs_task(self, value: asyncio.Task) -> None:
        if self._update_camera_configs_task is None or self._update_camera_configs_task.done():
            self._update_camera_configs_task = value
            return
        else:
            logger.warning("Camera connection task already running! Ignoring request...")

    @property
    def detect_available_cameras_task(self) -> asyncio.Task:
        return self._detect_available_cameras_task

    @detect_available_cameras_task.setter
    def detect_available_cameras_task(self, value: asyncio.Task) -> None:
        if self._detect_available_cameras_task is None or self._detect_available_cameras_task.done():
            self._detect_available_cameras_task = value
            return
        else:
            logger.warning("Camera detection task already running! Ignoring request...")

    @property
    def close_cameras_task(self) -> asyncio.Task:
        return self._close_cameras_task

    @close_cameras_task.setter
    def close_cameras_task(self, value: asyncio.Task) -> None:
        if self._close_cameras_task is None or self._close_cameras_task.done():
            self._close_cameras_task = value
            return
        else:
            logger.warning("Camera close task already running! Ignoring request...")


