import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.wrangling.frame_listener_worker import FrameEscaperWorker
from skellycam.core.frames.wrangling.frame_saver_process import FrameSaverProcess

logger = logging.getLogger(__name__)


@dataclass
class FrameWrangler:
    camera_group_dto: CameraGroupDTO
    frame_escaper: FrameEscaperWorker
    frame_saver: FrameSaverProcess

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
               frame_saver_config_queue: multiprocessing.Queue,
               frame_listener_config_queue: multiprocessing.Queue):

        return cls(frame_escaper=FrameEscaperWorker(camera_group_dto=camera_group_dto,
                                                    shmorc_dto=shmorc_dto,
                                                    new_configs_queue=frame_listener_config_queue,
                                                    use_thread=True),  # use a thread instead of a process for the listener, since its job is pretty simple

                   frame_saver=FrameSaverProcess(camera_group_dto=camera_group_dto,
                                                 multi_frame_escape_shm_dto=shmorc_dto.multi_frame_escape_shm_dto,
                                                 new_configs_queue=frame_saver_config_queue),  #this needs to be a process becuase saving is IO blocking
                   camera_group_dto=camera_group_dto)

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self.frame_escaper.start()
        self.frame_saver.start()

    def is_alive(self) -> bool:
        return self.frame_escaper.is_alive() or self.frame_saver.is_alive()

    def join(self):
        self.frame_escaper.join()
        self.frame_saver.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        if not self.camera_group_dto.ipc.kill_camera_group_flag.value == True and not self.camera_group_dto.ipc.global_kill_flag.value == True:
            raise ValueError("FrameWrangler was closed before the kill flag was set.")
        if self.is_alive():
            self.join()
        logger.debug(f"Frame wrangler closed")
