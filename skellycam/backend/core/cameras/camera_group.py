import asyncio
import logging
from typing import Coroutine, Callable, Optional

from skellycam.backend.core.cameras.camera_process_manager import (
    CameraProcessManager,
)
from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.frames.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
    ):
        self._camera_process_manager = CameraProcessManager()
        self._frame_wrangler = FrameWrangler()
        self._frame_loop_task: Optional[asyncio.Task] = None
        self._should_continue = True

    @property
    def camera_ids(self):
        return self._camera_process_manager.camera_ids

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._frame_wrangler.set_websocket_bytes_sender(ws_send_bytes)

    def set_camera_configs(self, camera_configs: CameraConfigs):
        logger.debug(f"Setting camera configs to {camera_configs}")
        self._camera_process_manager.set_camera_configs(camera_configs)
        self._frame_wrangler.set_camera_configs(camera_configs)

    @property
    def frame_wrangler(self) -> FrameWrangler:
        return self._frame_wrangler

    async def start_cameras(self):
        logger.info("Starting cameras...")
        self._camera_process_manager.start_cameras()
        self._frame_loop_task = asyncio.create_task(self._start_frame_loop())


    async def _start_frame_loop(self):
        logger.info(f"Frame capture loop cameras: {self.camera_ids} started.")
        while self._should_continue:
            new_frames = self._camera_process_manager.get_new_frames()
            if len(new_frames) > 0:
                await self._frame_wrangler.handle_new_frames(new_frames)
            else:
                await asyncio.sleep(0.001)
        logger.info("Frame capture loop has stopped.")

    async def update_configs(self, camera_configs: CameraConfigs, strict: bool = False):
        logger.info(f"Updating camera configs to {camera_configs}")
        await self._camera_process_manager.update_camera_configs(camera_configs=camera_configs,
                                                                 strict=strict)

    async def close(self):
        logger.debug("Closing camera group")
        self._frame_wrangler.close()
        self._camera_process_manager.close()
        self._should_continue = False
        await self._frame_loop_task

        logger.info("All cameras have stopped capturing")
