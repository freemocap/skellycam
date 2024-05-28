import logging
import multiprocessing
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_process import CameraProcess
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames

logger = logging.getLogger(__name__)


def start_cameras(camera_configs: CameraConfigs,
                  shared_memory_names: GroupSharedMemoryNames,
                  group_orchestrator: CameraGroupOrchestrator,
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, CameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = CameraProcess(config=config,
                                           shared_memory_names=shared_memory_names[camera_id],
                                           triggers=group_orchestrator.camera_triggers[camera_id],
                                           exit_event=exit_event
                                           )

    [camera.start() for camera in cameras.values()]
    group_orchestrator.wait_for_cameras_ready()

    return cameras
