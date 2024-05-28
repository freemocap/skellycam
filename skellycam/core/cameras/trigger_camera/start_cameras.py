import logging
import multiprocessing
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.cameras.trigger_camera.trigger_camera_process import TriggerCameraProcess
from skellycam.core.memory.camera_shared_memory import SharedMemoryNames

logger = logging.getLogger(__name__)


def start_cameras(camera_configs: CameraConfigs,
                  shared_memory_names: Dict[CameraId, SharedMemoryNames],
                  multicam_triggers: MultiCameraTriggerOrchestrator,
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, TriggerCameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = TriggerCameraProcess(config=config,
                                                  shared_memory_names=shared_memory_names[camera_id],
                                                  triggers=multicam_triggers.single_camera_triggers[camera_id],
                                                  exit_event=exit_event
                                                  )

    [camera.start() for camera in cameras.values()]
    multicam_triggers.wait_for_cameras_ready()

    return cameras
