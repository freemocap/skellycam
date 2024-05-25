import logging
import multiprocessing
from typing import Coroutine, Callable, Optional

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_trigger_process import MultiCameraTriggerProcess
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggers
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
    ):
        self._shm_lock = multiprocessing.Lock()

        self._multicam_triggers: Optional[MultiCameraTriggers] = None
        self._multi_camera_process: Optional[MultiCameraTriggerProcess] = None
        self._frame_wrangler = FrameWrangler()

    @property
    def camera_ids(self):
        if self._multi_camera_process is None:
            return []
        return self._multi_camera_process.camera_ids

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._frame_wrangler.set_websocket_bytes_sender(ws_send_bytes)

    def set_camera_configs(self, configs: CameraConfigs):
        logger.debug(f"Setting camera configs to {configs}")
        self._multicam_triggers = MultiCameraTriggers.from_camera_configs(configs)

        camera_shm = CameraSharedMemoryManager(camera_configs=configs,
                                               lock=self._shm_lock)

        self._multi_camera_process = MultiCameraTriggerProcess(camera_configs=configs,
                                                               shm_lock=self._shm_lock,
                                                               shared_memory_names=camera_shm.shared_memory_names,
                                                               multicam_triggers=self._multicam_triggers)

        self._frame_wrangler.set_camera_configs(configs=configs,
                                                multicam_triggers=self._multicam_triggers,
                                                shared_memory_names=camera_shm.shared_memory_names)

        camera_shm.close() #close the main thread's connection to the shared memory, but don't unlink (delete) it

    @property
    def frame_wrangler(self) -> FrameWrangler:
        return self._frame_wrangler

    async def start_cameras(self, number_of_frames: Optional[int] = None):
        self._multi_camera_process.start(number_of_frames=number_of_frames)
        self._frame_wrangler.start_frame_listener()

    async def update_configs(self, camera_configs: CameraConfigs):
        logger.info(f"Updating camera configs to {camera_configs}")
        await self._multi_camera_process.update_configs(camera_configs=camera_configs)
        self._frame_wrangler.set_camera_configs(camera_configs)

    async def close(self):
        logger.debug("Closing camera group")
        await self._frame_wrangler.close() if self._frame_wrangler else None
        await self._multi_camera_process.close() if self._multi_camera_process else None
        logger.info("Camera group closed.")
