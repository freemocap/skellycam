import logging
import multiprocessing
import time
from typing import List

import numpy as np

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


def camera_group_trigger_loop(
        camera_configs: CameraConfigs,
        group_orchestrator: CameraGroupOrchestrator,
        kill_camera_group_flag: multiprocessing.Value,
        global_kill_event: multiprocessing.Event
):
    loop_count = 0
    elapsed_per_loop_ns = []
    try:
        group_orchestrator.await_for_cameras_ready()
        group_orchestrator.fire_initial_triggers()

        logger.debug(f"Starting camera trigger loop for cameras: {group_orchestrator.camera_ids}...")
        while not kill_camera_group_flag.value and not global_kill_event.is_set():
            tik = time.perf_counter_ns()

            group_orchestrator.trigger_multi_frame_read()

            if loop_count > 0:
                elapsed_per_loop_ns.append((time.perf_counter_ns() - tik))
            loop_count += 1

        logger.debug(f"Multi-camera trigger loop for cameras: {group_orchestrator.camera_ids}  ended")
        wait_10ms()
        log_time_stats(
            camera_configs=camera_configs,
            elapsed_per_loop_ns=elapsed_per_loop_ns,
        )
    finally:
        logger.debug(f"Multi-camera trigger loop for cameras: {group_orchestrator.camera_ids}  exited")


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


