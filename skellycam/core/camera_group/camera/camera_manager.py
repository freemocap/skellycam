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
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraManager(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    orchestrator: CameraGroupOrchestrator
    camera_group_dto: CameraGroupDTO
    camera_processes: Dict[CameraId, CameraProcess]

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO):

        return cls(camera_group_dto=camera_group_dto,
                   orchestrator=camera_group_dto.shmorc_dto.camera_group_orchestrator,
                   camera_processes={camera_id: CameraProcess(camera_id=camera_id,
                                                              dto=camera_group_dto,
                                                              ) for camera_id in
                                     camera_group_dto.camera_ids()},
                   )

    @property
    def camera_ids(self):
        return self.camera_group_dto.camera_ids

    def start(self):
        logger.info(f"Starting cameras: {list(self.camera_group_dto.camera_configs.keys())}")

        [camera.start() for camera in self.camera_processes.values()]

        self.camera_group_frame_loop()
        logger.success(f"Cameras {self.camera_ids} frame loop ended.")

    def close(self):
        logger.info(f"Stopping cameras: {self.camera_ids}")
        self.camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
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

    def camera_group_frame_loop(self):
        self.orchestrator.await_for_cameras_ready()

        loop_count = 0
        elapsed_per_loop_ns = []
        try:
            self.orchestrator.await_for_cameras_ready()
            self.orchestrator.signal_frame_loop_started()

            logger.debug(f"Starting camera trigger loop for cameras: {self.shmorchestrator.camera_ids}...")

            while not self.camera_group_dto.ipc_flags.global_kill_flag.value and not self.camera_group_dto.ipc_flags.kill_camera_group_flag.value:
                tik = time.perf_counter_ns()

                # Trigger all cameras to read a frame
                self.shmorchestrator.trigger_multi_frame_read()

                # Check for new camera configs
                if self.camera_group_dto.config_update_queue.qsize() > 0:
                    logger.trace(
                        f"Config update queue has items, pausing frame loop to update configs")
                    self.shmorchestrator.pause_loop()

                    update_instructions = self.camera_group_dto.config_update_queue.get()

                    self.update_camera_configs(update_instructions)
                    self.shmorchestrator.unpause_loop()

                if loop_count > 0:
                    elapsed_per_loop_ns.append((time.perf_counter_ns() - tik))
                loop_count += 1

            logger.debug(f"Multi-camera trigger loop for cameras: {self.shmorchestrator.camera_ids}  ended")
            wait_10ms()
            log_time_stats(
                camera_configs=self.camera_group_dto.camera_configs,
                elapsed_per_loop_ns=elapsed_per_loop_ns,
            )
        finally:
            logger.debug(f"Multi-camera trigger loop for cameras: {self.shmorchestrator.camera_ids}  exited")


def log_time_stats(camera_configs: CameraConfigs,
                   elapsed_per_loop_ns: List[int]):
    number_of_cameras = len(camera_configs)
    resolution = str(camera_configs[0].resolution)
    number_of_frames = len(elapsed_per_loop_ns) + 1
    ideal_frame_rate = min([camera_config.framerate for camera_config in camera_configs.values()])

    logger.info(
        f"Read {number_of_frames} x {resolution} images read from {number_of_cameras} camera(s):"
        f"\n\tMEASURED FRAME RATE (ideal: {ideal_frame_rate} fps): "
        f"\n\t\tmean   : {(1e9 / np.mean(elapsed_per_loop_ns)):.2f} fps "
        f"\n\t\tmedian : {(1e9 / np.median(elapsed_per_loop_ns)):.2f} fps \n"
        f"\n\tTime elapsed per multi-frame loop  (ideal: {(ideal_frame_rate ** -1) * 1e3:.2f} ms) -  "
        f"\n\t\tmean(std)   : {np.mean(elapsed_per_loop_ns) / 1e6:.2f} ({np.std(elapsed_per_loop_ns) / 1e6:.2f}) ms"
        f"\n\t\tmedian(mad) : {np.median(elapsed_per_loop_ns) / 1e6:.2f} ({np.median(np.abs(elapsed_per_loop_ns - np.median(elapsed_per_loop_ns))) / 1e6:.2f}) ms"
    )