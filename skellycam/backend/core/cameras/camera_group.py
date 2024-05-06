import logging
from typing import Coroutine, Callable, Optional

from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.cameras.trigger_camera.camera_trigger_process import CameraTriggerProcess
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_wrangler import FrameWrangler
from skellycam.backend.core.frames.shared_image_memory import SharedImageMemoryManager

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
    ):
        self._multi_camera_process: Optional[CameraTriggerProcess] = None
        # self._multi_camera_process =  CameraProcessManager()
        self._frame_wrangler = FrameWrangler()
        self._shared_memory_manager: Optional[SharedImageMemoryManager] = None

    @property
    def camera_ids(self):
        if self._multi_camera_process is None:
            return []
        return self._multi_camera_process.camera_ids

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._frame_wrangler.set_websocket_bytes_sender(ws_send_bytes)

    def set_camera_configs(self, camera_configs: CameraConfigs):
        logger.debug(f"Setting camera configs to {camera_configs}")
        resolutions = [config.resolution for config in camera_configs.values()]
        if not all(res == resolutions[0] for res in resolutions):
            # TODO: Support different resolutions
            raise ValueError("All cameras must have the same resolution for the shared memory thing to work (for now)")

        self._shared_memory_manager = SharedImageMemoryManager(image_resolution=resolutions[0])
        self._multi_camera_process = CameraTriggerProcess(camera_configs=camera_configs,
                                                          frame_pipe=self._frame_wrangler.get_frame_input_pipe(),
                                                          shared_memory_name=self._shared_memory_manager.shared_memory_name)
        self._frame_wrangler.set_camera_configs(camera_configs,
                                                shared_memory_manager=self._shared_memory_manager)

    @property
    def frame_wrangler(self) -> FrameWrangler:
        return self._frame_wrangler

    async def start_cameras(self):
        self._multi_camera_process.start()

    async def update_configs(self, camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs to {camera_configs}")
        await self._multi_camera_process.update_configs(camera_configs=camera_configs)
        self._frame_wrangler.set_camera_configs(camera_configs)

    async def close(self):
        logger.debug("Closing camera group")
        self._frame_wrangler.close()
        await self._multi_camera_process.close()
        logger.info("Camera group closed.")
