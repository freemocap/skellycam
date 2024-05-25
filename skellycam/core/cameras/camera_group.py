import logging
import multiprocessing
from typing import Optional

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_trigger_process import MultiCameraTriggerProcess
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
            self,
    ):
        self._exit_event = multiprocessing.Event()
        self._shm_lock = multiprocessing.Lock()

        self._multicam_triggers: Optional[MultiCameraTriggerOrchestrator] = None
        self._camera_shm_manager: Optional[CameraSharedMemoryManager] = None
        self._multi_camera_process: Optional[MultiCameraTriggerProcess] = None
        self._frame_wrangler = FrameWrangler(exit_event=self._exit_event)

    @property
    def camera_ids(self):
        if self._multi_camera_process is None:
            return []
        return self._multi_camera_process.camera_ids

    def set_camera_configs(self, configs: CameraConfigs):
        logger.debug(f"Setting camera configs to {configs}")
        self._multicam_triggers = MultiCameraTriggerOrchestrator.from_camera_configs(configs)

        self._camera_shm_manager = CameraSharedMemoryManager(camera_configs=configs,
                                                             lock=self._shm_lock)

        self._multi_camera_process = MultiCameraTriggerProcess(camera_configs=configs,
                                                               shm_lock=self._shm_lock,
                                                               shared_memory_names=self._camera_shm_manager.shared_memory_names,
                                                               multicam_triggers=self._multicam_triggers,
                                                               exit_event=self._exit_event, )

        self._frame_wrangler.set_camera_info(camera_configs=configs,
                                             shm_lock=self._shm_lock,
                                             shared_memory_names=self._camera_shm_manager.shared_memory_names,
                                             multicam_triggers=self._multicam_triggers)

    async def start_cameras(self, number_of_frames: Optional[int] = None):
        self._multi_camera_process.start(number_of_frames=number_of_frames)
        self._frame_wrangler.start_frame_listener()

    async def close(self):
        logger.debug("Closing camera group")
        if self._frame_wrangler:
            self._frame_wrangler.close()
        if self._multi_camera_process:
            self._multi_camera_process.close()
        if self._camera_shm_manager:
            self._camera_shm_manager.close_and_unlink()
        logger.info("Camera group closed.")
