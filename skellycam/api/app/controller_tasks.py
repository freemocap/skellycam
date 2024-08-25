import asyncio
import logging

from skellycam.api.app.app_state import get_app_state, TaskStatus

logger = logging.getLogger(__name__)


class ControllerTasks:
    def __init__(self):
        self._task_awaiters: list[asyncio.Task] = []

        self._connect_to_cameras_task: asyncio.Task = asyncio.create_task(asyncio.sleep(0), name="ConnectToCameras")
        self._detect_available_cameras_task: asyncio.Task = asyncio.create_task(asyncio.sleep(0),
                                                                                name="DetectAvailableCameras")
        self._close_cameras_task: asyncio.Task = asyncio.create_task(asyncio.sleep(0), name="CloseCameras")

        self._add_task_awaiter(self._connect_to_cameras_task)
        self._add_task_awaiter(self._detect_available_cameras_task)
        self._add_task_awaiter(self._close_cameras_task)

    @property
    async def connect_to_cameras_task(self) -> asyncio.Task:
        return self._connect_to_cameras_task

    @connect_to_cameras_task.setter
    def connect_to_cameras_task(self, value: asyncio.Task) -> None:
        if self._connect_to_cameras_task is None or self._connect_to_cameras_task.done():
            self._connect_to_cameras_task = value
            self._add_task_awaiter(self._connect_to_cameras_task)
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
            self._add_task_awaiter(self._detect_available_cameras_task)
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
            self._add_task_awaiter(self._close_cameras_task)
            return
        else:
            logger.warning("Camera close task already running! Ignoring request...")

    def _add_task_awaiter(self, task: asyncio.Task) -> None:
        self._task_awaiters.append(asyncio.create_task(await_task(task)))


async def await_task(task: asyncio.Task) -> None:
    if not task:
        raise ValueError("Task is None!")
    get_app_state().update_task_status(TaskStatus.from_task(task))
    await task
    get_app_state().update_task_status(TaskStatus.from_task(task))
