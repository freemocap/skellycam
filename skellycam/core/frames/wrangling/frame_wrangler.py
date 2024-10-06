import logging
import multiprocessing

from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.wrangling.frame_listener_process import FrameListenerProcess
from skellycam.core.frames.wrangling.frame_router_process import FrameRouterProcess
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO

logger = logging.getLogger(__name__)


class FrameWrangler:

    def __init__(self,
                 group_shm_dto: CameraGroupSharedMemoryDTO,
                 shm_valid_flag: multiprocessing.Value,
                 group_orchestrator: CameraGroupOrchestrator,
                 ipc_queue: multiprocessing.Queue,
                 record_frames_flag: multiprocessing.Value,
                 kill_camera_group_flag: multiprocessing.Value,
                 global_kill_event: multiprocessing.Event):
        self._ipc_queue = ipc_queue
        self._record_frames_flag = record_frames_flag
        self._kill_camera_group_flag = kill_camera_group_flag

        frame_escape_pipe_entrance, frame_escape_pipe_exit = multiprocessing.Pipe()

        self._listener_process = FrameListenerProcess(
            group_shm_dto=group_shm_dto,
            shm_valid_flag=shm_valid_flag,
            group_orchestrator=group_orchestrator,
            frame_escape_pipe=frame_escape_pipe_entrance,
            ipc_queue=ipc_queue,
            kill_camera_group_flag=self._kill_camera_group_flag,
            global_kill_event=global_kill_event,
        )

        self._frame_router_process = FrameRouterProcess(
            camera_configs=group_shm_dto.camera_configs,
            frame_escape_pipe=frame_escape_pipe_exit,
            ipc_queue=ipc_queue,
            record_frames_flag=self._record_frames_flag,
            kill_camera_group_flag=self._kill_camera_group_flag,
            global_kill_event=global_kill_event,
        )

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self._listener_process.start()
        self._frame_router_process.start()

    def is_alive(self) -> bool:
        return self._listener_process.is_alive() and self._frame_router_process.is_alive()

    def join(self):
        self._listener_process.join()
        self._frame_router_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._record_frames_flag.value = False
        self._kill_camera_group_flag.value = True
        if self.is_alive():
            self.join()
        logger.debug(f"Frame wrangler closed")
