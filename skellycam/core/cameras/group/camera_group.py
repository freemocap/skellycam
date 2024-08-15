import logging
from multiprocessing import Queue
from multiprocessing.synchronize import Event as MultiprocessingEvent
from typing import Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_process import CameraGroupProcess
from skellycam.core.consumers.frame_consumer_process import FrameConsumerProcess

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            consumer_queue: Queue,  # TODO: include in tests
            exit_event: MultiprocessingEvent,
    ):
        self._exit_event = exit_event
        self._process: Optional[CameraGroupProcess] = None

        self._consumer_queue = consumer_queue

    @property
    def camera_ids(self):
        if self._process is None:
            return []
        return self._process.camera_ids

    def set_camera_configs(self, configs: CameraConfigs):
        logger.debug(f"Setting camera configs to {configs}")
        self._process = CameraGroupProcess(camera_configs=configs,
                                           consumer_queue=self._consumer_queue,
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
