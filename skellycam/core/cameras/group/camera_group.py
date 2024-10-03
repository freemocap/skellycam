import logging
import multiprocessing
import os
from typing import Optional

from skellycam.api.app.app_state import AppState, SubProcessStatus, get_app_state
from skellycam.core.cameras.group.camera_group_process import CameraGroupProcess
from skellycam.core.cameras.group.update_instructions import UpdateInstructions

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            ipc_queue: multiprocessing.Queue,
            process_kill_event: multiprocessing.Event,
    ):
        self._update_queue = multiprocessing.Queue()  # Update camera configs
        self._ipc_queue = ipc_queue
        self._process = CameraGroupProcess(config_update_queue=self._update_queue,
                                           ipc_queue=self._ipc_queue,
                                           process_kill_event=process_kill_event,
                                           )
        self._app_state: AppState = get_app_state()

    async def start(self, number_of_frames: Optional[int] = None):
        logger.info("Starting camera group")
        await self._process.start()
        self._ipc_queue.put(
            SubProcessStatus.from_process(self._process.process, parent_pid=os.getpid()))

    async def close(self):
        logger.debug("Closing camera group")
        self._app_state.kill_camera_group_flag.value = True
        if self._process:
            await self._process.close()
        self._ipc_queue.put(
            SubProcessStatus.from_process(self._process.process, parent_pid=os.getpid()))
        logger.info("Camera group closed.")

    async def update_camera_configs(self, update_instructions: UpdateInstructions):
        logger.debug(
            f"Updating Camera Configs with instructions: {update_instructions}")
        self._update_queue.put(update_instructions)
