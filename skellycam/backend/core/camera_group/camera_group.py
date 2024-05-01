import asyncio
import logging
import time
from typing import Dict, Coroutine, Callable

from skellycam.backend.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.backend.core.camera_group.strategies.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from skellycam.backend.core.camera_group.strategies.strategies import (
    Strategy,
)
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            camera_configs: Dict[CameraId, CameraConfig],
            ws_send_bytes: Callable[[bytes], Coroutine],
            strategy: Strategy = Strategy.X_CAM_PER_PROCESS,
    ):
        logger.info(
            f"Creating camera group with strategy {strategy} and camera configs {camera_configs}"
        )
        self._strategy_enum = strategy
        self._camera_configs = camera_configs

        self._strategy_class = self._resolve_strategy()

        self._frame_wrangler = FrameWrangler(
            camera_configs=self._camera_configs,
            ws_send_bytes=ws_send_bytes,
        )

        self._should_continue = True

    @property
    def frame_wrangler(self) -> FrameWrangler:
        return self._frame_wrangler


    async def start_frame_loop(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._strategy_enum}")

        self._strategy_class.start_capture()

        while self._should_continue:
            new_frames = self._strategy_class.get_new_frames()
            if len(new_frames) > 0:
                await self._frame_wrangler.handle_new_frames(new_frames)
            else:
                await asyncio.sleep(0.01)

    def update_configs(self, camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs to {camera_configs}")
        self._camera_configs = camera_configs
        self._strategy_class.update_camera_configs(camera_configs)


    def _resolve_strategy(self):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(camera_configs=self._camera_configs)

    def close(self):
        logger.debug("Closing camera group")
        self._frame_wrangler.stop()
        self._strategy_class.stop_capture()
        logger.info("All cameras have stopped capturing")
