import logging
import multiprocessing
import time
from typing import Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.trigger_camera_process import TriggerCameraProcess

logger = logging.getLogger(__name__)


def start_cameras(camera_configs: CameraConfigs,
                  shared_memory_names: Dict[CameraId, str],
                  lock: multiprocessing.Lock,
                  initial_triggers: Dict[CameraId, multiprocessing.Event],
                  grab_frame_triggers: Dict[CameraId, multiprocessing.Event],
                  frame_grabbed_triggers: Dict[CameraId, multiprocessing.Event],
                  retrieve_frame_triggers: Dict[CameraId, multiprocessing.Event],
                  camera_ready_events: Dict[CameraId, multiprocessing.Event],
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, TriggerCameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = trigger_camera_factory(config=config,
                                                    shared_memory_name=shared_memory_names[camera_id],
                                                    lock=lock,
                                                    initial_trigger=initial_triggers[camera_id],
                                                    grab_frame_trigger=grab_frame_triggers[camera_id],
                                                    frame_grabbed_trigger=frame_grabbed_triggers[camera_id],
                                                    retrieve_frame_trigger=retrieve_frame_triggers[camera_id],
                                                    camera_ready_event=camera_ready_events[camera_id],
                                                    exit_event=exit_event
                                                    )

    [camera.start() for camera in cameras.values()]
    wait_for_cameras_ready(camera_ready_events)
    logger.success(f"All cameras connected and ready - {list(camera_ready_events.keys())}")
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


def wait_for_cameras_ready(camera_ready_events: Dict[CameraId, multiprocessing.Event]):
    while not all([camera_ready_event.is_set() for camera_ready_event in camera_ready_events.values()]):
        logger.trace("Waiting for all cameras to be ready...")
        time.sleep(1)
        for camera_id, camera_ready_event in camera_ready_events.items():
            if camera_ready_event.is_set():
                logger.debug(f"Camera {camera_id} is ready!")

    logger.debug("All cameras are ready!")
