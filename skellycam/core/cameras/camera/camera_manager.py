import logging
import multiprocessing
import threading
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_process import CameraProcess
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.cameras.group.update_instructions import UpdateInstructions
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self,
                 group_shm_dto: CameraGroupSharedMemoryDTO,
                 shm_valid_flag: multiprocessing.Value,
                 group_orchestrator: CameraGroupOrchestrator,
                 kill_camera_group_flag: multiprocessing.Value,
                 global_kill_event: multiprocessing.Event
                 ):
        self._kill_camera_group_flag = kill_camera_group_flag
        self._camera_configs = group_shm_dto.camera_configs
        self._group_orchestrator = group_orchestrator
        self._camera_processes: Dict[CameraId, CameraProcess] = {}

        for camera_id, config in self._camera_configs.items():
            self._camera_processes[camera_id] = CameraProcess(config=config,
                                                              camera_triggers=group_orchestrator.camera_triggers[
                                                                  camera_id],
                                                              shared_memory_names=group_shm_dto.group_shm_names[
                                                                  camera_id],
                                                              shm_valid_flag=shm_valid_flag,
                                                              kill_camera_group_flag=kill_camera_group_flag,
                                                              global_kill_event=global_kill_event,
                                                              )

    @property
    def camera_ids(self):
        return list(self._camera_configs.keys())

    def start_cameras(self):
        logger.info(f"Starting cameras: {list(self._camera_configs.keys())}")

        [camera.start() for camera in self._camera_processes.values()]

        self._group_orchestrator.await_for_cameras_ready()
        logger.success(f"Cameras {self.camera_ids} started successfully!")

    def close(self):
        logger.info(f"Stopping cameras: {self.camera_ids}")
        self._kill_camera_group_flag.value = True
        self._close_cameras()

    def update_camera_configs(self, update_instructions: UpdateInstructions):
        logger.debug(f"Updating cameras with instructions: {update_instructions}")
        for camera_id in update_instructions.update_these_cameras:
            self._camera_processes[camera_id].update_config(update_instructions.new_configs[camera_id])

    def _close_cameras(self):
        logger.debug(f"Closing cameras: {self.camera_ids}")

        camera_close_threads = []
        for camera_process in self._camera_processes.values():
            camera_close_threads.append(threading.Thread(target=camera_process.close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]

        while any([camera_process.is_alive() for camera_process in self._camera_processes.values()]):
            wait_10ms()

        # self.register_subprocess()

        for camera_id in self.camera_ids:
            self._camera_processes.pop(camera_id)
            self._camera_configs.pop(camera_id)
            self._group_orchestrator.camera_triggers.pop(camera_id)

        logger.trace(f"Cameras closed: {self.camera_ids}")
