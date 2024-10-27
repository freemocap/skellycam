import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.wrangling.frame_listener_process import FrameListenerProcess
from skellycam.core.frames.wrangling.frame_router_process import FrameRouterProcess

logger = logging.getLogger(__name__)


@dataclass
class FrameWrangler:
    camera_group_dto: CameraGroupDTO
    listener_process: FrameListenerProcess
    frame_router_process: FrameRouterProcess

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
               frame_router_config_queue: multiprocessing.Queue,
               frame_listener_config_queue: multiprocessing.Queue):

        return cls(listener_process=FrameListenerProcess(camera_group_dto=camera_group_dto,
                                                         shmorc_dto=shmorc_dto,
                                                         new_configs_queue=frame_listener_config_queue),

                   frame_router_process=FrameRouterProcess(camera_group_dto=camera_group_dto,
                                                           shmorc_dto=shmorc_dto,
                                                           new_configs_queue=frame_router_config_queue),
                   camera_group_dto=camera_group_dto)

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self.listener_process.start()
        self.frame_router_process.start()

    def is_alive(self) -> bool:
        return self.listener_process.is_alive() or self.frame_router_process.is_alive()

    def join(self):
        self.listener_process.join()
        self.frame_router_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        if not self.camera_group_dto.ipc_flags.kill_camera_group_flag.value == True and not self.camera_group_dto.ipc_flags.global_kill_flag.value == True:
            raise ValueError("FrameWrangler was closed before the kill flag was set.")
        if self.is_alive():
            self.join()
        logger.debug(f"Frame wrangler closed")
