import logging
import threading
import time
from typing import Dict, List

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.camera_process import CameraProcess
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.utilities.wait_functions import wait_10ms, wait_100ms

logger = logging.getLogger(__name__)


class CameraManager(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    orchestrator: CameraGroupOrchestrator
    camera_group_dto: CameraGroupDTO
    camera_processes: Dict[CameraId, CameraProcess]

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO):

        return cls(camera_group_dto=camera_group_dto,
                   orchestrator=shmorc_dto.camera_group_orchestrator,
                   camera_processes={camera_id: CameraProcess.create(camera_id=camera_id,
                                                                     camera_group_dto=camera_group_dto,
                                                                     shmorc_dto=shmorc_dto
                                                                     ) for camera_id in
                                     camera_group_dto.camera_ids},
                   )

    @property
    def camera_ids(self):
        return self.camera_group_dto.camera_ids

    def start(self):
        logger.info(f"Starting cameras: {list(self.camera_group_dto.camera_configs.keys())}")

        [camera.start() for camera in self.camera_processes.values()]
        self.orchestrator.await_cameras_ready()
        self.camera_group_frame_loop()
        logger.success(f"Cameras {self.camera_ids} frame loop ended.")

    def join(self):
        [camera.join() for camera in self.camera_processes.values()]

    def camera_group_frame_loop(self):
        self.orchestrator.await_cameras_ready()

        loop_count = 0
        elapsed_per_loop_ns = []
        try:

            logger.debug(f"Starting camera trigger loop for cameras: {self.camera_ids}...")

            while not self.camera_group_dto.ipc.global_kill_flag.value and not self.camera_group_dto.ipc.kill_camera_group_flag.value:

                tik = time.perf_counter_ns()

                self._check_handle_config_update()

                # Trigger all cameras to read a frame
                self.orchestrator.trigger_multi_frame_read()

                if loop_count > 0:
                    elapsed_per_loop_ns.append((time.perf_counter_ns() - tik))
                loop_count += 1

            logger.debug(f"Multi-camera trigger loop for cameras: {self.camera_ids}  ended")
            wait_10ms()
            log_time_stats(
                camera_configs=self.camera_group_dto.camera_configs,
                elapsed_per_loop_ns=elapsed_per_loop_ns,
            )
        finally:
            logger.debug(f"Multi-camera trigger loop for cameras: {self.camera_ids}  exited")
            self._close_cameras()

    def _check_handle_config_update(self):
        # Check for new camera configs
        if not self.camera_group_dto.update_queue.empty():
            logger.trace(f"Handling camera config updates for cameras: {self.camera_ids}")
            update_instructions = self.camera_group_dto.update_queue.get()

            self.update_camera_configs(update_instructions)
            while any(
                    [not camera_process.new_config_queue.empty() for camera_process in self.camera_processes.values()]):
                wait_100ms()
            self.orchestrator.await_cameras_ready()
            logger.trace(f"Camera configs updated for cameras: {self.camera_ids}")

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


def log_time_stats(camera_configs: CameraConfigs,
                   elapsed_per_loop_ns: List[int]):
    number_of_cameras = len(camera_configs)
    resolution = str(camera_configs[0].resolution)
    number_of_frames = len(elapsed_per_loop_ns) + 1
    ideal_framerate = min([camera_config.framerate for camera_config in camera_configs.values()])

    logger.info(
        f"Read {number_of_frames} x {resolution} images read from {number_of_cameras} camera(s):"
        f"\n\tMEASURED FRAME RATE (ideal: {ideal_framerate} fps): "
        f"\n\t\tmean   : {(1e9 / np.mean(elapsed_per_loop_ns)):.2f} fps "
        f"\n\t\tmedian : {(1e9 / np.median(elapsed_per_loop_ns)):.2f} fps \n"
        f"\n\tTime elapsed per multi-frame loop  (ideal: {(ideal_framerate ** -1) * 1e3:.2f} ms) -  "
        f"\n\t\tmean(std)   : {np.mean(elapsed_per_loop_ns) / 1e6:.2f} ({np.std(elapsed_per_loop_ns) / 1e6:.2f}) ms"
        f"\n\t\tmedian(mad) : {np.median(elapsed_per_loop_ns) / 1e6:.2f} ({np.median(np.abs(elapsed_per_loop_ns - np.median(elapsed_per_loop_ns))) / 1e6:.2f}) ms"
    )
