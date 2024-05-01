import asyncio
import logging
from typing import Dict, Coroutine, Callable

from skellycam.backend.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.backend.core.camera_group.camera_process_manager import (
    CameraProcessManager,
)
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
            camera_configs: Dict[CameraId, CameraConfig],
            ws_send_bytes: Callable[[bytes], Coroutine],
    ):
        logger.info(
            f"Creating camera group with camera configs {camera_configs}"
        )
        self._camera_process_manager = CameraProcessManager(camera_configs=camera_configs)

        self._frame_wrangler = FrameWrangler(
            camera_configs=camera_configs,
            ws_send_bytes=ws_send_bytes,
        )

        self._should_continue = True

    @property
    def frame_wrangler(self) -> FrameWrangler:
        return self._frame_wrangler

    async def start_frame_loop(self):
        logger.info(f"Starting camera group processes")

        self._camera_process_manager.start_capture()

        while self._should_continue:
            new_frames = self._camera_process_manager.get_new_frames()
            if len(new_frames) > 0:
                await self._frame_wrangler.handle_new_frames(new_frames)
            else:
                await asyncio.sleep(0.001)

    def update_configs(self, camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs to {camera_configs}")
        self._camera_process_manager.update_camera_configs(camera_configs)

    def close(self):
        logger.debug("Closing camera group")
        self._frame_wrangler.stop()
        self._camera_process_manager.stop_capture()
        logger.info("All cameras have stopped capturing")
