import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.ring_buffer_camera_group_shared_memory import \
    RingBufferCameraGroupSharedMemory
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    SingleSlotCameraGroupSharedMemory
from skellycam.core.frames.wrangling.frame_listener_process import FrameListenerProcess
from skellycam.core.frames.wrangling.frame_router_process import FrameRouterProcess

logger = logging.getLogger(__name__)


@dataclass
class FrameWrangler:
    camera_group_dto: CameraGroupDTO
    listener_process: FrameListenerProcess
    frame_router_process: FrameRouterProcess
    frame_escape_ring_shm: SingleSlotCameraGroupSharedMemory

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
               frame_router_config_queue: multiprocessing.Queue,
               frame_listener_config_queue: multiprocessing.Queue):

        frame_escape_ring_shm = RingBufferCameraGroupSharedMemory.create(camera_group_dto=camera_group_dto,
                                                                         read_only=True)

        return cls(listener_process=FrameListenerProcess(camera_group_dto=camera_group_dto,
                                                         shmorc_dto=shmorc_dto,
                                                         new_configs_queue=frame_listener_config_queue,
                                                         frame_escape_ring_shm_dto=frame_escape_ring_shm.to_dto()),

                   frame_router_process=FrameRouterProcess(camera_group_dto=camera_group_dto,
                                                           new_configs_queue=frame_router_config_queue,
                                                           frame_escape_ring_shm_dto=frame_escape_ring_shm.to_dto()),
                   camera_group_dto=camera_group_dto,
                   frame_escape_ring_shm=frame_escape_ring_shm)

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
        if not self.dto.ipc_flags.kill_camera_group_flag.value == True and not self.dto.ipc_flags.global_kill_flag.value == True:
            raise ValueError("FrameWrangler was closed before the kill flag was set.")
        if self.is_alive():
            self.join()
        self.frame_escape_ring_shm.close_and_unlink()
        logger.debug(f"Frame wrangler closed")
