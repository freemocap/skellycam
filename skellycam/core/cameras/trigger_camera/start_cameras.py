import logging
import multiprocessing
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.cameras.trigger_camera.trigger_camera_process import TriggerCameraProcess

logger = logging.getLogger(__name__)


def start_cameras(camera_configs: CameraConfigs,
                  shared_memory_names: Dict[CameraId, str],
                  lock: multiprocessing.Lock,
                  multicam_triggers: MultiCameraTriggerOrchestrator,
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, TriggerCameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = trigger_camera_factory(config=config,
                                                    shared_memory_name=shared_memory_names[camera_id],
                                                    lock=lock,
                                                    camera_triggers=multicam_triggers.single_camera_triggers[camera_id],
                                                    exit_event=exit_event
                                                    )

    [camera.start() for camera in cameras.values()]
    multicam_triggers.wait_for_cameras_ready()

    return cameras


def trigger_camera_factory(config: CameraConfig,
                           shared_memory_name: str,
                           lock: multiprocessing.Lock,
                           camera_triggers: SingleCameraTriggers,
                           exit_event: multiprocessing.Event
                           ) -> TriggerCameraProcess:
    return TriggerCameraProcess(config=config,
                                shared_memory_name=shared_memory_name,
                                lock=lock,
                                triggers=camera_triggers,
                                exit_event=exit_event
                                )
