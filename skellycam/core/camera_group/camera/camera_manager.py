import logging
import threading
import time
from typing import List

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera_group.camera.camera_process import CameraProcess
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, CameraIdString
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.utilities.wait_functions import wait_10ms, wait_100ms

logger = logging.getLogger(__name__)

MAX_CAMERA_PORTS_TO_CHECK = 20


class CameraManager(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    orchestrator: CameraGroupOrchestrator
    camera_group_dto: CameraGroupDTO
    camera_processes: dict[CameraIdString, CameraProcess] = {}

    @property
    def camera_ids(self):
        return list(self.camera_processes.keys())

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO):

        camera_processes = {}
        for camera_id, camera_config in camera_group_dto.camera_configs.items():
            frame_loop_flags = shmorc_dto.camera_group_orchestrator.frame_loop_flags[camera_id]
            camera_shm_dto = shmorc_dto.frame_loop_shm_dto.camera_shm_dtos[camera_id]
            camera_processes[camera_id] = CameraProcess.create(camera_id=camera_id,
                                                               camera_config=camera_config,
                                                               camera_group_dto=camera_group_dto,
                                                               frame_loop_flags=frame_loop_flags,
                                                               camera_shared_memory_dto=camera_shm_dto)

        return cls(camera_group_dto=camera_group_dto,
                   orchestrator=shmorc_dto.camera_group_orchestrator,
                   camera_processes=camera_processes
                   )

    def start(self):
        if len(self.camera_ids) == 0:
            raise ValueError("No cameras to start!")

        logger.info(f"Starting camera manager for cameras: {self.camera_ids}...")

        [camera.start() for camera in self.camera_processes.values()]
        self._config_update_listener_loop()
        logger.info(f"Cameras {self.camera_ids} frame loop ended.")

    def _config_update_listener_loop(self):

        try:
            while self.camera_group_dto.should_continue:
                self._check_handle_config_update()
                wait_10ms()
            logger.trace(f"Camera config update listener loop for cameras: {self.camera_ids} exited")
        finally:
            logger.debug(f"Closing camera manager for cameras: {self.camera_ids}...")
            self.close()

    def _check_handle_config_update(self):
        # Check for new camera configs
        if not self.camera_group_dto.ipc.update_camera_configs_queue.empty():
            logger.trace(f"Handling camera config updates for cameras: {self.camera_ids}")
            update_instructions = self.camera_group_dto.ipc.update_camera_configs_queue.get()

            self.update_camera_configs(update_instructions)
            while any(
                    [not camera_process.new_config_queue.empty() for camera_process in
                     self.camera_processes.values()]) and self.camera_group_dto.should_continue:
                wait_100ms()
            self.orchestrator.await_cameras_ready()
            logger.trace(f"Camera configs updated for cameras: {self.camera_ids}")

    def close(self):
        logger.info(f"Stopping cameras: {self.camera_ids}")
        if not self.camera_group_dto.ipc.kill_camera_group_flag.value and not self.camera_group_dto.ipc.global_kill_flag.value:
            logger.warning("Camera group was closed without kill flag set!")
            self.camera_group_dto.ipc.kill_camera_group_flag.value = True
        self._close_cameras()

    def update_camera_configs(self, update_instructions: UpdateInstructions):
        logger.debug(f"Updating cameras with instructions: {update_instructions}")
        for camera_id in update_instructions.update_these_cameras:
            self.camera_processes[camera_id].update_config(update_instructions.new_configs[camera_id])

    def _close_cameras(self):
        logger.debug(f"Closing cameras: {self.camera_ids}")

        camera_close_threads = []
        for camera_process in self.camera_processes.values():
            camera_close_threads.append(threading.Thread(target=camera_process.close))
        [thread.start() for thread in camera_close_threads]
        [thread.join() for thread in camera_close_threads]

        while any([camera_process.is_alive() for camera_process in self.camera_processes.values()]):
            wait_10ms()

        logger.trace(f"Cameras closed: {self.camera_ids}")


