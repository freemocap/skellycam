import asyncio
import logging
import multiprocessing
import time
from typing import Dict, List

from skellycam.backend.core.camera_group.strategies.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from skellycam.backend.core.camera_group.strategies.strategies import (
    Strategy,
)
from skellycam.backend.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload
from skellycam.backend.core.frames.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)


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

        self._frame_wrangler = FrameWrangler(
            camera_configs=self._camera_configs,
        )

    @property
    def frame_wrangler(self) -> FrameWrangler:
        return self._frame_wrangler

    @property
    def any_capturing(self):
        for is_capturing_event in self._is_capturing_events_by_camera.values():
            if is_capturing_event.is_set():
                return True
        return False

    async def start_frame_loop(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")

        self._strategy_class.start_capture()
        await self._wait_for_cameras_to_start()
        while self.any_capturing:
            new_frames = self._strategy_class.get_new_frames()
            if len(new_frames) > 0:
                await self._frame_wrangler.handle_new_frames(new_frames)
            else:
                await asyncio.sleep(0.001)


    def update_configs(self, camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs to {camera_configs}")
        self._camera_configs = camera_configs
        self._strategy_class.update_camera_configs(camera_configs)

    async def _wait_for_cameras_to_start(self, restart_process_if_it_dies: bool = True):
        logger.debug(f"Waiting for camera {self._camera_configs.keys()} to start")

        while (
            not self._all_cameras_ready_event.is_set()
            and not self._close_cameras_event.is_set()
        ):
            time.sleep(1.0)
            camera_started_check = dict.fromkeys(self._camera_configs.keys(), False)

            for camera_id, event in self._is_capturing_events_by_camera.items():
                camera_started_check[camera_id] = event.is_set()
            logger.debug(f"Camera started? {camera_started_check}")

            if all(list(camera_started_check.values())):
                logger.info(f"All cameras {list(self._camera_configs.keys())} started!")
                self._all_cameras_ready_event.set()  # start frame capture on all core

    def _resolve_strategy(self):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(
                camera_configs=self._camera_configs,
                is_capturing_events_by_camera=self._is_capturing_events_by_camera,
                close_cameras_event=self._close_cameras_event,
                all_cameras_ready_event=self._all_cameras_ready_event,
            )

    def close(self):
        logger.debug("Closing camera group")
        self._close_cameras_event.set()
        self._frame_wrangler.stop()
        while self.any_capturing:
            logger.trace("Waiting for cameras to stop capturing")
            time.sleep(0.1)
        logger.info("All cameras have stopped capturing")

    def _create_events(self):
        self._close_cameras_event = multiprocessing.Event()
        self._all_cameras_ready_event = multiprocessing.Event()
        self._is_capturing_events_by_camera = {
            camera_id: multiprocessing.Event()
            for camera_id in self._camera_configs.keys()
        }
