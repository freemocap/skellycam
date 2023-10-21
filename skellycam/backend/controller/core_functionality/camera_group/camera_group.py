import multiprocessing
import time
from typing import Dict, List

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.strategies.grouped_process_strategy import \
    GroupedProcessStrategy
from skellycam.backend.controller.core_functionality.camera_group.strategies.strategies import Strategy
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class CameraGroup:
    def __init__(
            self,
            camera_configs: Dict[CameraId, CameraConfig],
            strategy: Strategy = Strategy.X_CAM_PER_PROCESS,
    ):
        self._all_cameras_ready_event = None
        self._close_cameras_event = None
        logger.info(
            f"Creating camera group with strategy {strategy} and camera configs {camera_configs}"
        )
        self._event_dictionary = None
        self._strategy_enum = strategy
        self._camera_configs = camera_configs
        self._strategy_class = self._resolve_strategy()

    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def close_cameras_event(self):
        return self._close_cameras_event


    def update_configs(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.info(f"Updating camera configs to {camera_configs}")
        self._camera_configs = camera_configs
        self._strategy_class.update_camera_configs(camera_configs)

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")
        self._close_cameras_event = multiprocessing.Event()
        self._all_cameras_ready_event = multiprocessing.Event()
        self._event_dictionary = {"all_cameras_ready": self._all_cameras_ready_event,
                                  "close_cameras": self._close_cameras_event}
        self._strategy_class.start_capture(
            event_dictionary=self._event_dictionary,
        )

        self._wait_for_cameras_to_start()

    def _wait_for_cameras_to_start(self, restart_process_if_it_dies: bool = True):
        logger.trace(f"Waiting for cameras {self._camera_configs.keys()} to start")
        all_cameras_started = False
        while not all_cameras_started:
            time.sleep(0.5)
            camera_started_dictionary = dict.fromkeys(self._camera_configs.keys(), False)

            for camera_id in self._camera_configs.keys():
                camera_started_dictionary[camera_id] = self.check_if_camera_is_ready(
                    camera_id
                )

            logger.trace(f"Camera started? {camera_started_dictionary}")
            all_cameras_started = all(list(camera_started_dictionary.values()))

        logger.success(f"All cameras {list(self._camera_configs.keys())} started!")
        self._all_cameras_ready_event.set()  # start frame capture on all cameras

    def check_if_camera_is_ready(self, cam_id: str):
        return self._strategy_class.check_if_camera_is_ready(cam_id)


    def new_frames(self) -> List[FramePayload]:
        return self._strategy_class.get_new_frames()

    def _resolve_strategy(self):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(camera_configs=self._camera_configs)

    def close(self):
        logger.debug("Closing camera group")
        self._close_cameras_event.set()
        while self.is_capturing:
            logger.trace("Waiting for cameras to close...")
            time.sleep(0.5)
