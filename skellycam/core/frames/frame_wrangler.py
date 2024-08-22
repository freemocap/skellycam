import logging
import multiprocessing
import os

from skellycam.api.app.app_state import ProcessStatus
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.frame_listener_process import FrameListenerProcess, STOP_RECORDING_SIGNAL
from skellycam.core.frames.frame_saver_process import FrameSaverProcess
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames

logger = logging.getLogger(__name__)


class FrameWrangler:

    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_shm_names: GroupSharedMemoryNames,
                 group_orchestrator: CameraGroupOrchestrator,
                 frontend_pipe: multiprocessing.Pipe,
                 update_queue: multiprocessing.Queue,
                 process_status_update_queue: multiprocessing.Queue,
                 record_frames_flag: multiprocessing.Value,
                 kill_camera_group_flag: multiprocessing.Value, ):
        super().__init__()
        self._config_update_queue = update_queue
        self._process_status_update_queue = process_status_update_queue
        self._kill_camera_group_flag = kill_camera_group_flag

        camera_configs: CameraConfigs = camera_configs
        group_orchestrator: CameraGroupOrchestrator = group_orchestrator

        self._video_recorder_queue = multiprocessing.Queue()
        self._listener_process = FrameListenerProcess(
            camera_configs=camera_configs,
            group_orchestrator=group_orchestrator,
            group_shm_names=group_shm_names,
            video_recorder_queue=self._video_recorder_queue,
            frontend_pipe=frontend_pipe,
            record_frames_flag=record_frames_flag,
            kill_camera_group_flag=self._kill_camera_group_flag,
        )
        self._video_recorder_process = FrameSaverProcess(
            video_recorder_queue=self._video_recorder_queue,
            frontend_pipe=frontend_pipe,
            camera_configs=camera_configs,
            kill_camera_group_flag=self._kill_camera_group_flag,
        )


    def start(self):
        logger.debug(f"Starting frame listener process...")
        self._listener_process.start()
        self._video_recorder_process.start()
        self.update_process_states()

    def update_process_states(self):
        self._process_status_update_queue.put(
            ProcessStatus.from_process(self._listener_process.process, parent_pid=os.getpid()))
        self._process_status_update_queue.put(
            ProcessStatus.from_process(self._video_recorder_process.process, parent_pid=os.getpid()))


    def is_alive(self) -> bool:
        if self._listener_process is None or self._video_recorder_process is None:
            return False
        return self._listener_process.is_alive() and self._video_recorder_process.is_alive()

    def join(self):
        self._listener_process.join()
        self._video_recorder_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._kill_camera_group_flag.value = True
        self._video_recorder_queue.put(STOP_RECORDING_SIGNAL)
        if self.is_alive():
            self.join()
        self._video_recorder_queue.close()
        self.update_process_states()
        logger.debug(f"Frame wrangler closed")
