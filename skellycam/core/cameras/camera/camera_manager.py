import logging
import multiprocessing
import os
import threading
from typing import Optional, List, Dict

from skellycam.api.app.app_state import ProcessStatus
from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_process import CameraProcess
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.cameras.group.update_instructions import UpdateInstructions
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 shared_memory_names: GroupSharedMemoryNames,
                 group_orchestrator: CameraGroupOrchestrator,
                 ipc_queue: multiprocessing.Queue,
                 kill_camera_group_flag: multiprocessing.Value, ):
        self._kill_camera_group_flag = kill_camera_group_flag
        self._camera_configs = camera_configs
        self._shared_memory_names = shared_memory_names
        self._group_orchestrator = group_orchestrator
        self._ipc_queue = ipc_queue
        self._camera_processes: Dict[CameraId, CameraProcess] = {}

        for camera_id, config in camera_configs.items():
            self._camera_processes[camera_id] = CameraProcess(config=config,
                                                              triggers=group_orchestrator.camera_triggers[camera_id],
                                                              shared_memory_names=shared_memory_names[camera_id],
                                                              kill_camera_group_flag=kill_camera_group_flag,
                                                              )

    @property
    def camera_ids(self):
        return list(self._camera_configs.keys())

    def start_cameras(self):
        logger.info(f"Starting cameras: {list(self._camera_configs.keys())}")

        [camera.start() for camera in self._camera_processes.values()]

        self._update_process_state()

        self._group_orchestrator.await_for_cameras_ready()
        logger.success(f"Cameras {self.camera_ids} started successfully!")

    def _update_process_state(self):
        for camera in self._camera_processes.values():
            self._ipc_queue.put(ProcessStatus.from_process(camera.process, parent_pid=os.getpid()))

    def close(self):
        logger.info(f"Stopping cameras: {self.camera_ids}")
        self._close_cameras()
        self._kill_camera_group_flag.value = True
        self._update_process_state()

    def update_camera_configs(self, update_instructions: UpdateInstructions):
        logger.debug(f"Updating cameras with instructions: {update_instructions}")
        self._close_cameras(update_instructions.close_these_cameras)
        for camera_id in update_instructions.update_these_cameras:
            self._camera_processes[camera_id].update_config(update_instructions.new_configs[camera_id])

    def _close_cameras(self, close_these_cameras: Optional[List[CameraId]] = None):
        if not close_these_cameras:
            close_these_cameras = self.camera_ids
        logger.debug(f"Closing cameras: {close_these_cameras}")

        camera_close_threads = []
        for camera_id in close_these_cameras:
            camera_close_threads.append(threading.Thread(target=self.camera_processes[camera_id].close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]
        for camera_id in close_these_cameras:
            del self.camera_processes[camera_id]
            del self.update_queues[camera_id]

        logger.trace(f"Cameras closed: {close_these_cameras}")
