import logging
import multiprocessing
import os

from skellycam.api.app.app_state import SubProcessStatus
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.wrangling.frame_listener_process import FrameListenerProcess
from skellycam.core.frames.wrangling.frame_router_process import FrameRouterProcess
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames

logger = logging.getLogger(__name__)


class FrameWrangler:

    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_shm_names: GroupSharedMemoryNames,
                 group_orchestrator: CameraGroupOrchestrator,
                 frontend_relay_pipe: multiprocessing.Pipe,
                 update_queue: multiprocessing.Queue,
                 ipc_queue: multiprocessing.Queue,
                 record_frames_flag: multiprocessing.Value,
                 kill_camera_group_flag: multiprocessing.Value, ):
        super().__init__()
        self._config_update_queue = update_queue
        self._ipc_queue = ipc_queue
        self._record_frames_flag = record_frames_flag
        self._kill_camera_group_flag = kill_camera_group_flag

        camera_configs: CameraConfigs = camera_configs
        group_orchestrator: CameraGroupOrchestrator = group_orchestrator

        self._frame_escape_pipe_entrance, self._frame_escape_pipe_exit = multiprocessing.Pipe()

        self._listener_process = FrameListenerProcess(
            camera_configs=camera_configs,
            group_orchestrator=group_orchestrator,
            group_shm_names=group_shm_names,
            frame_escape_pipe_entrance=self._frame_escape_pipe_entrance,
            record_frames_flag=self._record_frames_flag,
            kill_camera_group_flag=self._kill_camera_group_flag,
        )
        self._frame_router_process = FrameRouterProcess(
            camera_configs=camera_configs,
            frame_escape_pipe_exit=self._frame_escape_pipe_exit,
            frontend_relay_pipe=frontend_relay_pipe,
            record_frames_flag=self._record_frames_flag,
            kill_camera_group_flag=self._kill_camera_group_flag,
        )

    def start(self):
        logger.debug(f"Starting frame listener process...")
        self._listener_process.start()
        self._frame_router_process.start()
        self._update_process_states()

    def _update_process_states(self):
        self._ipc_queue.put(SubProcessStatus.from_process(self._listener_process.process, parent_pid=os.getpid()))
        self._ipc_queue.put(
            SubProcessStatus.from_process(self._frame_router_process.process, parent_pid=os.getpid()))

    def is_alive(self) -> bool:
        if self._listener_process is None or self._frame_router_process is None:
            return False
        return self._listener_process.is_alive() and self._frame_router_process.is_alive()

    def join(self):
        self._listener_process.join()
        self._frame_router_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._kill_camera_group_flag.value = True
        self._record_frames_flag.value = False
        if self.is_alive():
            self.join()
        self._update_process_states()
        logger.debug(f"Frame wrangler closed")