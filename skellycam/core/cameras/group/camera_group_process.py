import logging
import multiprocessing
from multiprocessing import Process
from typing import Optional

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory

logger = logging.getLogger(__name__)


class CameraGroupProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            exit_event: multiprocessing.Event,
    ):
        self._camera_configs = camera_configs
        self._exit_event = exit_event

        self._process: Optional[Process] = None

    def _create_process(self, number_of_frames: Optional[int] = None):
        self._process = Process(
            name="MultiCameraTriggerProcess",
            target=CameraGroupProcess._run_process,
            args=(self._camera_configs,
                  self._exit_event,
                  number_of_frames
                  )
        )

    @staticmethod
    def _run_process(configs: CameraConfigs,
                     exit_event: multiprocessing.Event,
                     number_of_frames: Optional[int] = None
                     ):
        group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=configs)

        group_shm = CameraGroupSharedMemory.create(camera_configs=configs)

        frame_wrangler = FrameWrangler(exit_event=exit_event,
                                       camera_configs=configs,
                                       group_shm_names=group_shm.shared_memory_names,
                                       group_orchestrator=group_orchestrator)
        frame_wrangler.start_frame_listener()
        # if self._frame_wrangler:
        #     self._frame_wrangler.close()
        logger.debug(f"CameraTriggerProcess started")
        camera_group_trigger_loop(camera_configs=configs,
                                  group_orchestrator=group_orchestrator,
                                  group_shm_names=group_shm.shared_memory_names,
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
