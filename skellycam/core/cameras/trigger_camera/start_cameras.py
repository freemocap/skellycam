import logging
import multiprocessing
import time
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggers
from skellycam.core.cameras.trigger_camera.trigger_camera_process import TriggerCameraProcess

logger = logging.getLogger(__name__)


def start_cameras(camera_configs: CameraConfigs,
                  shared_memory_names: Dict[CameraId, str],
                  lock: multiprocessing.Lock,
                  multicam_triggers: MultiCameraTriggers,
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, TriggerCameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = trigger_camera_factory(config=config,
                                                    shared_memory_name=shared_memory_names[camera_id],
                                                    lock=lock,
                                                    camera_triggers=multicam_triggers.to_single_camera(camera_id),
                                                    exit_event=exit_event
                                                    )

    [camera.start() for camera in cameras.values()]
    multicam_triggers.wait_for_cameras_ready()

    return cameras


def trigger_camera_factory(config: CameraConfig,
                           shared_memory_name: str,
                           lock: multiprocessing.Lock,
                           initial_trigger: multiprocessing.Event,
                           grab_frame_trigger: multiprocessing.Event,
                           frame_grabbed_trigger: multiprocessing.Event,
                           retrieve_frame_trigger: multiprocessing.Event,
                           camera_ready_event: multiprocessing.Event,
                           exit_event: multiprocessing.Event
                           ) -> TriggerCameraProcess:

    return TriggerCameraProcess(config=config,
                                shared_memory_name=shared_memory_name,
                                lock=lock,
                                initial_trigger=initial_trigger,
                                grab_frame_trigger=grab_frame_trigger,
                                frame_grabbed_trigger=frame_grabbed_trigger,
                                retrieve_frame_trigger=retrieve_frame_trigger,
                                camera_ready_event=camera_ready_event,
                                exit_event=exit_event
                                )



