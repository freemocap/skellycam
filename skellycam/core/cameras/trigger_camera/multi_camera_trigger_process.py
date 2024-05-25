import logging
import multiprocessing
from multiprocessing import Process
from typing import Optional, Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_trigger_loop import multi_camera_trigger_loop
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator

logger = logging.getLogger(__name__)


class MultiCameraTriggerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            multicam_triggers: MultiCameraTriggerOrchestrator,
            shm_lock: multiprocessing.Lock,
            shared_memory_names: Dict[CameraId, str],
            exit_event: multiprocessing.Event,
    ):
        self._camera_configs = camera_configs
        self._multicam_triggers = multicam_triggers
        self._shm_lock = shm_lock
        self._shared_memory_names = shared_memory_names
        self._exit_event = exit_event

        self._process: Optional[Process] = None

    def _create_process(self, number_of_frames: Optional[int] = None):
        self._process = Process(
            name="MultiCameraTriggerProcess",
            target=MultiCameraTriggerProcess._run_process,
            args=(self._camera_configs,
                  self._multicam_triggers,
                  self._shared_memory_names,
                  self._shm_lock,
                  self._exit_event,
                  number_of_frames
                  )
        )

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     multicam_triggers: MultiCameraTriggerOrchestrator,
                     shared_memory_names: Dict[CameraId, str],
                     shm_lock: multiprocessing.Lock,
                     exit_event: multiprocessing.Event,
                     number_of_frames: Optional[int] = None
                     ):
        logger.debug(f"CameraTriggerProcess started")
        multi_camera_trigger_loop(camera_configs=camera_configs,
                                  multicam_triggers=multicam_triggers,
                                  shared_memory_names=shared_memory_names,
                                  shm_lock=shm_lock,
                                  exit_event=exit_event,
                                  number_of_frames=number_of_frames,
                                  )

        logger.debug(f"CameraTriggerProcess completed")

    def start(self, number_of_frames: Optional[int] = None):
        logger.debug("Stating CameraTriggerProcess...")
        self._create_process(number_of_frames=number_of_frames)
        self._process.start()

    def update_configs(self, camera_configs: CameraConfigs):
        raise NotImplementedError("Update configs not implemented")
        # self._camera_configs = camera_configs
        # self._update_pipe_sender.put(camera_configs)

    def close(self):
        logger.debug("Closing CameraTriggerProcess...")
        self._exit_event.set()
        if self._process is not None:
            self._process.join()
        logger.debug("CameraTriggerProcess closed")

    @property
    def camera_ids(self) -> [CameraId]:
        return [CameraId(camera_id) for camera_id in self._camera_configs.keys()]
