import logging
import multiprocessing
import time
from typing import Optional, List, Dict

import numpy as np

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.cameras.trigger_camera.start_cameras import start_cameras
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


def multi_camera_trigger_loop(
        camera_configs: CameraConfigs,
        multicam_triggers: MultiCameraTriggerOrchestrator,
        shared_memory_names: Dict[CameraId, str],
        exit_event: multiprocessing.Event,
        number_of_frames: Optional[int] = None,
):
    logger.debug(f"Starting camera trigger loop for cameras: {list(camera_configs.keys())}")

    cameras = start_cameras(
        camera_configs=camera_configs,
        shared_memory_names=shared_memory_names,
        multicam_triggers=multicam_triggers,
        exit_event=exit_event,
    )

    logger.info(f"Camera trigger loop started for cameras: {list(camera_configs.keys())}")

    multicam_triggers.fire_initial_triggers()

    loop_count = 0
    elapsed_in_trigger_ns = []
    elapsed_per_loop_ns = []
    logger.debug(f"Starting multi-camera trigger loop for cameras: {list(cameras.keys())}")
    while not exit_event.is_set():
        tik = time.perf_counter_ns()

        multicam_triggers.trigger_multi_frame_read()

        if number_of_frames is not None:
            check_loop_count(number_of_frames, loop_count, exit_event)

        elapsed_in_trigger_ns.append((time.perf_counter_ns() - tik))
        loop_count += 1

        elapsed_per_loop_ns.append((time.perf_counter_ns() - tik))

    logger.debug(f"Multi-camera trigger loop for cameras: {list(cameras.keys())}  ended")
    wait_10ms()
    log_time_stats(
        camera_configs=camera_configs,
        elapsed_in_trigger_ns=elapsed_in_trigger_ns,
        elapsed_per_loop_ns=elapsed_per_loop_ns,
    )


def log_time_stats(camera_configs: CameraConfigs, elapsed_in_trigger_ns: List[int], elapsed_per_loop_ns: List[int]):
    number_of_cameras = len(camera_configs)
    resolution = str(camera_configs[0].resolution)
    number_of_frames = len(elapsed_per_loop_ns)
    ideal_framerate = min([camera_config.framerate for camera_config in camera_configs.values()])

    logger.info(
        f"Read {number_of_frames} x {resolution} images read from {number_of_cameras} camera(s):"
        f"\n\tTime elapsed per multi-frame loop  (ideal: {(ideal_framerate ** -1) / 1e6:.2f} ms) -  "
        f"\n\t\tmean   : {np.mean(elapsed_per_loop_ns) / 1e6:.2f} ms"
        f"\n\t\tmedian : {np.median(elapsed_per_loop_ns) / 1e6:.2f} ms"
        f"\n\t\tstd-dev: {np.std(elapsed_per_loop_ns) / 1e6:.2f} ms\n"
        f"\n\tTime elapsed in during multi-camera `grab` trigger (ideal: 0 ms) - "
        f"\n\t\tmean   : {np.mean(elapsed_in_trigger_ns) / 1e6:.2f} ms"
        f"\n\t\tmedian : {np.median(elapsed_in_trigger_ns) / 1e6:.2f} ms"
        f"\n\t\tstd-dev: {np.std(elapsed_in_trigger_ns) / 1e6:.2f} ms\n"
        f"\n\tMEASURED FRAMERATE (ideal: {ideal_framerate} fps): "
        f"\n\t\tmean   : {(1e9 / np.mean(elapsed_per_loop_ns)):.2f} fps "
        f"\n\t\tmedian : {(1e9 / np.median(elapsed_per_loop_ns)):.2f} fps \n"
    )


def check_loop_count(number_of_frames: int, loop_count: int, exit_event: multiprocessing.Event):
    if number_of_frames is not None:
        if loop_count + 1 >= number_of_frames:
            logger.trace(f"Reached number of frames: {number_of_frames} - setting `exit` event")
            exit_event.set()
