import logging
import multiprocessing
from typing import Optional

from skellycam.api.routes.websocket.frontend_payload_queue import get_frontend_payload_queue
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_process import CameraGroupProcess

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
    ):
        self._exit_event = multiprocessing.Event()
        self._process: Optional[CameraGroupProcess] = None

    @property
    def camera_ids(self):
        if self._process is None:
            return []
        return self._process.camera_ids

    def set_camera_configs(self, configs: CameraConfigs):
        logger.debug(f"Setting camera configs to {configs}")
        self._process = CameraGroupProcess(camera_configs=configs,
                                           frontend_payload_queue=get_frontend_payload_queue(),
                                           exit_event=self._exit_event, )

    async def start(self, number_of_frames: Optional[int] = None):
        logger.info("Starting camera group")
        if self._exit_event.is_set():
            self._exit_event.clear()  # Reset the exit event if this is a restart
        self._process.start(number_of_frames=number_of_frames)

    async def close(self):
        logger.debug("Closing camera group")
        if self._process:
            self._process.close()
        logger.info("Camera group closed.")

    def set_frontend_payload_queue(self, fe_queue: multiprocessing.Queue):
        self._fe_queue = fe_queue
