import asyncio
import logging
import multiprocessing
from typing import Optional, List, Union

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group import (
    CameraGroup,
)
from skellycam.core.consumers.frame_consumer_process import FrameConsumerProcess
from skellycam.core.detection.detect_available_devices import AvailableDevices, detect_available_devices

logger = logging.getLogger(__name__)


class Controller:
    def __init__(self,
                 ) -> None:
        super().__init__()
        self._camera_configs: Optional[CameraConfigs] = None
        """ 
        # TODO: the frame consumer seems like it should be part of the controller, but passing it down through 
        CameraGroup -> CameraGroupProcess -> FrameWrangler 
        seems clunky. Is there a better place for it to live/way to pass it down?

        We technically only need to pass down the consumer queue, but that is still less than ideal

        FrameConsumer could use an exit_event, but that is created by CameraGroup
        """
        self._exit_event = multiprocessing.Event()
        self._frame_consumer = FrameConsumerProcess(exit_event=self._exit_event)  # TODO: include in tests
        self._camera_group = CameraGroup(consumer=self._frame_consumer, exit_event=self._exit_event)

    async def detect(self) -> AvailableDevices:
        logger.info(f"Detecting cameras...")
        available_devices = await detect_available_devices()

        if len(available_devices) == 0:
            logger.warning(f"No cameras detected!")
            return available_devices

        self._camera_configs = {}
        for camera_id in available_devices.keys():
            self._camera_configs[CameraId(camera_id)] = CameraConfig(camera_id=CameraId(camera_id))
        self._camera_group.set_camera_configs(self._camera_configs)
        return available_devices

    async def connect(self,
                      camera_configs: Optional[CameraConfigs] = None,
                      number_of_frames: Optional[int] = None) -> Union[bool, List[CameraId]]:
        logger.info(f"Connecting to available cameras...")

        if camera_configs:
            self._camera_configs = camera_configs
            self._camera_group.set_camera_configs(camera_configs)
        else:
            logger.info(f"Available cameras not set - Executing `detect` method...")
            if not await self.detect():
                raise ValueError("No cameras detected!")

        await self._start_camera_group(number_of_frames=number_of_frames)
        return self._camera_group.camera_ids

    async def _start_camera_group(self, number_of_frames: Optional[int] = None):
        logger.debug(f"Starting camera group with cameras: {self._camera_group.camera_ids}")
        if self._camera_configs is None or len(self._camera_configs) == 0:
            raise ValueError("No cameras available to start camera group!")
        
        logger.info("Starting consumer process")
        self._frame_consumer.start_process()

        # logger.info("Starting logging task")
        # logging_monitor_task = asyncio.create_task(self._frame_consumer.monitor_logging_queue())

        logger.info("Starting camera group")
        await self._camera_group.start(number_of_frames=number_of_frames)

        # logger.info("awaiting logging monitor task")
        # await logging_monitor_task

    async def close(self):
        logger.debug(f"Closing camera group...")
        if self._camera_group is not None:
            await self._camera_group.close()

        logger.info("Setting exit event")
        self._exit_event.set()
        self._frame_consumer.close()
        


CONTROLLER = None


def create_controller() -> Controller:
    global CONTROLLER
    if not CONTROLLER:
        CONTROLLER = Controller()
    return CONTROLLER


def get_controller() -> Controller:
    global CONTROLLER
    if not isinstance(CONTROLLER, Controller):
        raise ValueError("Controller not created!")
    return CONTROLLER
