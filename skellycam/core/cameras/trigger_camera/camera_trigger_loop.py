import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import Dict, Optional

import numpy as np

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.trigger_camera import TriggerCameraProcess
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

logger = logging.getLogger(__name__)


def trigger_camera_factory(config: CameraConfig,
                           shared_memory_name: str,
                           lock: multiprocessing.Lock,
                           grab_frame_trigger: multiprocessing.Event,
                           frame_grabbed_trigger: multiprocessing.Event,
                           retrieve_frame_trigger: multiprocessing.Event,
                           ready_event: multiprocessing.Event,
                           exit_event: multiprocessing.Event
                           ) -> TriggerCameraProcess:
    return TriggerCameraProcess(config=config,
                                shared_memory_name=shared_memory_name,
                                lock=lock,
                                grab_frame_trigger=grab_frame_trigger,
                                frame_grabbed_trigger=frame_grabbed_trigger,
                                retrieve_frame_trigger=retrieve_frame_trigger,
                                ready_event=ready_event,
                                exit_event=exit_event
                                )


def start_cameras(camera_configs: CameraConfigs,
                  shared_memory_names: Dict[CameraId, str],
                  lock: multiprocessing.Lock,
                  grab_frame_triggers: Dict[CameraId, multiprocessing.Event],
                  frame_grabbed_triggers: Dict[CameraId, multiprocessing.Event],
                  retrieve_frame_triggers: Dict[CameraId, multiprocessing.Event],
                  ready_events: Dict[CameraId, multiprocessing.Event],
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, TriggerCameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = trigger_camera_factory(config=config,
                                                    shared_memory_name=shared_memory_names[camera_id],
                                                    lock=lock,
                                                    grab_frame_trigger=grab_frame_triggers[camera_id],
                                                    frame_grabbed_trigger=frame_grabbed_triggers[camera_id],
                                                    retrieve_frame_trigger=retrieve_frame_triggers[camera_id],
                                                    ready_event=ready_events[camera_id],
                                                    exit_event=exit_event
                                                    )

    [camera.start() for camera in cameras.values()]
    wait_for_cameras_ready(ready_events)
    logger.success(f"All cameras connected and ready - {list(ready_events.keys())}")
    return cameras


def wait_for_cameras_ready(ready_events: Dict[CameraId, multiprocessing.Event]):
    while not all([ready_event.is_set() for ready_event in ready_events.values()]):
        logger.trace("Waiting for all cameras to be ready...")
        time.sleep(1)
        for camera_id, ready_event in ready_events.items():
            if ready_event.is_set():
                logger.debug(f"Camera {camera_id} is ready!")

    logger.debug("All cameras are ready!")


def camera_trigger_loop(camera_configs: CameraConfigs,
                        shared_memory_names: Dict[CameraId, str],
                        lock: multiprocessing.Lock,
                        number_of_frames: Optional[int],
                        exit_event: multiprocessing.Event,
                        ):
    logger.debug(f"Starting camera trigger loop for cameras: {list(camera_configs.keys())}")

    ready_events = {CameraId(camera_id): multiprocessing.Event() for camera_id in camera_configs.keys()}
    grab_frame_triggers = {CameraId(camera_id): multiprocessing.Event() for camera_id in camera_configs.keys()}
    frame_grabbed_triggers = {CameraId(camera_id): multiprocessing.Event() for camera_id in camera_configs.keys()}
    retrieve_frame_triggers = {CameraId(camera_id): multiprocessing.Event() for camera_id in camera_configs.keys()}

    cameras = start_cameras(camera_configs=camera_configs,
                            lock=lock,
                            shared_memory_names=shared_memory_names,
                            grab_frame_triggers=grab_frame_triggers,
                            frame_grabbed_triggers=frame_grabbed_triggers,
                            retrieve_frame_triggers=retrieve_frame_triggers,
                            ready_events=ready_events,
                            exit_event=exit_event
                            )
    logger.info(f"Camera trigger loop started for cameras: {list(camera_configs.keys())}")
    payload = MultiFramePayload.create()

    while True:
        if all([ready_event.is_set() for ready_event in ready_events.values()]):
            logger.debug("All cameras are ready - sending initial `trigger` event")
            for trigger in grab_frame_triggers.values():
                trigger.set()
            break
        else:
            logger.trace("Waiting for all cameras to be ready...")
            time.sleep(1)
    loop_count = 0
    elapsed_ms = []
    while not exit_event.is_set():
        tik = time.perf_counter_ns()
        while not all([not trigger.is_set() for trigger in grab_frame_triggers.values()]):
            time.sleep(0.001)


        trigger_multi_frame_read(grab_frame_triggers=grab_frame_triggers,
                                 frame_grabbed_triggers=frame_grabbed_triggers,
                                 retrieve_frame_triggers=retrieve_frame_triggers)

        check_loop_count(number_of_frames, loop_count, exit_event, tik)
        elapsed_ms.append((time.perf_counter_ns() - tik) / 1e6)
        loop_count += 1

    print(f"Average loop time: {np.mean(elapsed_ms):.3f}ms - stddev: {np.std(elapsed_ms):.3f}ms")
    logger.debug(f"Closing camera trigger loop for cameras: {list(cameras.keys())}")


def trigger_multi_frame_read(grab_frame_triggers: Dict[CameraId, multiprocessing.Event],
                             frame_grabbed_triggers: Dict[CameraId, multiprocessing.Event],
                             retrieve_frame_triggers: Dict[CameraId, multiprocessing.Event]
                             ):
    # 1 - Trigger each camera should grab an image from the camera device with `cv2.VideoCapture.grab()` (which is faster than `cv2.VideoCapture.read()` as it does not decode the frame)
    for camera_id, grab_frame_trigger in grab_frame_triggers.items():
        if grab_frame_trigger.is_set():
            raise ValueError(f"Trigger is set for camera_id: {camera_id} - this should not happen!")
        grab_frame_trigger.set()

    # 2 - wait for all cameras to grab a frame
    while not all([frame_grabbed_trigger.is_set() for frame_grabbed_trigger in frame_grabbed_triggers.values()]):
        time.sleep(0.0001)

    # 3- Trigger each camera should retrieve the frame using `cv2.VideoCapture.retrieve()`, which decodes the frame into an image/numpy array
    for camera_id, retrieve_frame_triggers in retrieve_frame_triggers.items():
        if retrieve_frame_triggers.is_set():
            raise ValueError(f"Retrieve frame trigger for camera_id: {camera_id} is set - this should not happen!")
        retrieve_frame_triggers.set()


def check_loop_count(number_of_frames: int,
                     loop_count: int,
                     exit_event: multiprocessing.Event,
                     tik: int):

    if number_of_frames is not None:
        if loop_count+ 1 >= number_of_frames:
            logger.trace(f"Reached number of frames: {number_of_frames} - setting `exit` event")
            exit_event.set()





