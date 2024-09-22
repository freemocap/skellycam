import logging
import multiprocessing
import os
from typing import Optional

from skellycam.api.app.app_state import AppState, SubProcessStatus, get_app_state
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_process import CameraGroupProcess
from skellycam.core.cameras.group.update_instructions import UpdateInstructions

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            ipc_queue: multiprocessing.Queue,
    ):
        self._update_queue = multiprocessing.Queue()  # Update camera configs
        self._ipc_queue = ipc_queue
        self._process = CameraGroupProcess(config_update_queue=self._update_queue,
                                           ipc_queue=self._ipc_queue,
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

    async def update_camera_configs(self, new_configs: CameraConfigs, old_configs: CameraConfigs):
        if not self._process or not self._process.is_running:
            logger.warning("Cannot update camera configs - Camera group is not running")
            return

        update_instructions = UpdateInstructions.from_configs(new_configs=new_configs,
                                                              old_configs=old_configs)
        logger.debug(
            f"Sending new camera configs to camera group process: {new_configs}, update_instructions: {update_instructions}")
        self._update_queue.put(update_instructions)
