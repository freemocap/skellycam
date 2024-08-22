import multiprocessing
import threading
from typing import Optional, List, Dict

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_process import CameraProcess
from skellycam.core.cameras.camera.config import logger
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group import CameraGroupOrchestrator
from skellycam.core.cameras.group import UpdateInstructions
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames


class CameraManager:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 group_orchestrator: CameraGroupOrchestrator,
                 shared_memory_names: GroupSharedMemoryNames,
                 exit_event: multiprocessing.Event):
        self.exit_event = exit_event
        self.camera_configs = camera_configs
        self.shared_memory_names = shared_memory_names
        self.group_orchestrator = group_orchestrator
        self.camera_processes: Dict[CameraId, CameraProcess] = {}
        self.update_queues: Dict[CameraId, multiprocessing.Queue] = {}

        for camera_id, config in camera_configs.items():
            self.update_queues[camera_id] = multiprocessing.Queue()
            self.camera_processes[camera_id] = CameraProcess(config=config,
                                                             triggers=group_orchestrator.camera_triggers[camera_id],
                                                             shared_memory_names=shared_memory_names[camera_id],
                                                             update_queue=self.update_queues[camera_id],
                                                             exit_event=exit_event
                                                             )

    @property
    def camera_ids(self):
        return list(self.camera_configs.keys())

    def start_cameras(self):
        logger.info(f"Starting cameras: {list(self.camera_configs.keys())}")
        for camera in self.camera_processes.values():
            camera.start()
        self.group_orchestrator.await_for_cameras_ready()
        logger.success(f"Cameras {self.camera_ids} started successfully!")

    def close(self):
        logger.info(f"Stopping cameras: {self.camera_ids}")
        self._close_cameras()
        self.exit_event.set()

    def update_cameras(self, update_instructions: UpdateInstructions):
        logger.debug(f"Updating cameras with instructions: {update_instructions}")
        self._close_cameras(update_instructions.close_these_cameras)
        for camera_id in update_instructions.update_these_cameras:
            self.update_queues[camera_id].put(update_instructions.new_configs[camera_id])

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
