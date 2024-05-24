import logging
import multiprocessing
from multiprocessing import Process, connection
from typing import Optional, Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_trigger_loop import multi_camera_trigger_loop

logger = logging.getLogger(__name__)


class MultiCameraTriggerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            pipe_connection: connection.Connection,
    ):
        self._camera_configs = camera_configs
        self._pipe_connection = pipe_connection
        self._number_of_frames: Optional[int] = None
        self._process: Optional[Process] = None
        self._exit_event = multiprocessing.Event()

    def start(self, number_of_frames: Optional[int] = None):
        logger.debug("Stating CameraTriggerProcess...")
        self._number_of_frames = number_of_frames
        self._create_process()
        self._process.start()

    def update_configs(self, camera_configs: CameraConfigs):
        raise NotImplementedError("Update configs not implemented")
        # self._camera_configs = camera_configs
        # self._update_pipe_sender.put(camera_configs)

    async def close(self):
        logger.debug("Closing CameraTriggerProcess...")
        self._exit_event.set()
        if self._process is not None:
            self._process.join()
        logger.debug("CameraTriggerProcess closed")

    def _create_process(self):
        self._process = Process(
            name="MultiCameraTriggerProcess",
            target=MultiCameraTriggerProcess._run_process,
            args=(self._camera_configs,
                  self._pipe_connection,
                  self._exit_event,
                  self._number_of_frames,
                  )
        )

    @property
    def camera_ids(self) -> [CameraId]:
        return [CameraId(camera_id) for camera_id in self._camera_configs.keys()]

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     shared_memory_names: Dict[CameraId, str],
                     shm_lock: multiprocessing.Lock,
                     exit_event: multiprocessing.Event,
                     number_of_frames: Optional[int] = None
                     ):
        logger.debug(f"CameraTriggerProcess started")
        multi_camera_trigger_loop(camera_configs=camera_configs,
                                  shared_memory_names=shared_memory_names,
                                  shm_lock=shm_lock,
                                  exit_event=exit_event,
                                  number_of_frames=number_of_frames,
                                  )

        logger.debug(f"CameraTriggerProcess completed")
