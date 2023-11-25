import multiprocessing
import time
from typing import Dict, List

from skellycam.system.environment.get_logger import logger
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

        logger.info(
            f"Creating camera group with strategy {strategy} and camera configs {camera_configs}"
        )
        self._strategy_enum = strategy
        self._camera_configs = camera_configs

        self._create_events()
        self._strategy_class = self._resolve_strategy()

    @property
    def any_capturing(self):
        for is_capturing_event in self._is_capturing_events_by_camera.values():
            if is_capturing_event.is_set():
                return True
        return False

    def get_new_frames(self) -> List[FramePayload]:
        return self._strategy_class.get_new_frames()

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

        self._strategy_class.start_capture()

        self._wait_for_cameras_to_start()

    def _wait_for_cameras_to_start(self, restart_process_if_it_dies: bool = True):
        logger.trace(f"Waiting for cameras {self._camera_configs.keys()} to start")

        while not self._all_cameras_ready_event.is_set() and not self._close_cameras_event.is_set():
            time.sleep(1.0)
            camera_started_check = dict.fromkeys(self._camera_configs.keys(), False)

            for camera_id, event in self._is_capturing_events_by_camera.items():
                camera_started_check[camera_id] = event.is_set()
            logger.trace(f"Camera started? {camera_started_check}")

            if all(list(camera_started_check.values())):
                logger.success(f"All cameras {list(self._camera_configs.keys())} started!")
                self._all_cameras_ready_event.set()  # start frame capture on all cameras

    def _resolve_strategy(self):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(camera_configs=self._camera_configs,
                                          is_capturing_events_by_camera=self._is_capturing_events_by_camera,
                                          close_cameras_event=self._close_cameras_event,
                                          all_cameras_ready_event=self._all_cameras_ready_event)

    def close(self):
        logger.debug("Closing camera group")
        self._close_cameras_event.set()
        while self.any_capturing:
            logger.trace("Waiting for cameras to stop capturing")
            time.sleep(1.0)
        logger.info("All cameras have stopped capturing")

    def _create_events(self):
        self._close_cameras_event = multiprocessing.Event()
        self._all_cameras_ready_event = multiprocessing.Event()
        self._is_capturing_events_by_camera = {
            camera_id: multiprocessing.Event()
            for camera_id in self._camera_configs.keys()
        }
