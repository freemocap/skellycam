import asyncio
import logging
from typing import Optional

from skellycam.api.app.app_state import get_app_state, TaskStatus

logger = logging.getLogger(__name__)


class ControllerTasks:
    def __init__(self):
        self._connect_to_cameras_task: Optional[asyncio.Task] = None
        self._detect_available_cameras_task: Optional[asyncio.Task] = None
        self._close_cameras_task: Optional[asyncio.Task] = None
        self._task_awaiters: list[asyncio.Task] = []

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

    def add_task_awaiter(self, task: asyncio.Task) -> None:
        self._task_awaiters = [task for task in self._task_awaiters if not task.done()]
        self._task_awaiters.append(task)


async def await_task(task: Optional[asyncio.Task]) -> None:
    if task is not None:
        await task
        get_app_state().update_task_status(TaskStatus.from_task(task))
