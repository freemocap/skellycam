import logging
import multiprocessing
import time
from multiprocessing import shared_memory
from typing import Dict, Optional

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.trigger_camera import TriggerCameraProcess
from skellycam.core.detection.camera_id import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.shared_image_memory import SharedPayloadMemoryManager

logger = logging.getLogger(__name__)


def trigger_camera_factory(config: CameraConfig,
                           all_camera_ids: [CameraId],
                           shared_memory_name: str,
                           frame_queue: multiprocessing.Queue,
                           config_update_queue: multiprocessing.Queue,
                           get_frame_trigger: multiprocessing.Event,
                           ready_event: multiprocessing.Event,
                           exit_event: multiprocessing.Event
                           ) -> TriggerCameraProcess:
    return TriggerCameraProcess(config=config,
                                frame_queue=frame_queue,
                                config_update_queue=config_update_queue,
                                all_camera_ids=all_camera_ids,
                                shared_memory_name=shared_memory_name,
                                get_frame_trigger=get_frame_trigger,
                                ready_event=ready_event,
                                exit_event=exit_event
                                )


def start_cameras(camera_configs: CameraConfigs,
                  all_camera_ids: [CameraId],
                  shared_memory_name: str,
                  frame_queues: Dict[CameraId, multiprocessing.Queue],
                  config_update_queues: Dict[CameraId, multiprocessing.Queue],
                  trigger_events: Dict[CameraId, multiprocessing.Event],
                  ready_events: Dict[CameraId, multiprocessing.Event],
                  exit_event: multiprocessing.Event
                  ) -> Dict[CameraId, TriggerCameraProcess]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")

    cameras = {}
    for camera_id, config in camera_configs.items():
        cameras[camera_id] = trigger_camera_factory(config=config,
                                                    config_update_queue=config_update_queues[camera_id],
                                                    all_camera_ids=all_camera_ids,
                                                    shared_memory_name=shared_memory_name,
                                                    frame_queue=frame_queues[camera_id],
                                                    get_frame_trigger=trigger_events[camera_id],
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
                        multi_frame_pipe,  # send-only pipe connection
                        config_update_pipe,  # receive-only pipe connection
                        shared_memory_name: str,
                        number_of_frames: Optional[int],
                        exit_event: multiprocessing.Event,
                        ):
    logger.debug(f"Starting camera trigger loop for cameras: {list(camera_configs.keys())}")

    ready_events = {CameraId(camera_id): multiprocessing.Event() for camera_id in camera_configs.keys()}
    trigger_events = {CameraId(camera_id): multiprocessing.Event() for camera_id in camera_configs.keys()}
    frame_queues = {CameraId(camera_id): multiprocessing.Queue() for camera_id in camera_configs.keys()}
    config_update_queues = {CameraId(camera_id): multiprocessing.Queue() for camera_id in camera_configs.keys()}

    cameras = start_cameras(camera_configs=camera_configs,
                            all_camera_ids=list(camera_configs.keys()),
                            shared_memory_name=shared_memory_name,
                            frame_queues=frame_queues,
                            config_update_queues=config_update_queues,
                            trigger_events=trigger_events,
                            ready_events=ready_events,
                            exit_event=exit_event
                            )
    logger.info(f"Camera trigger loop started for cameras: {list(camera_configs.keys())}")
    payload = MultiFramePayload.create()

    while True:
        if all([ready_event.is_set() for ready_event in ready_events.values()]):
            logger.debug("All cameras are ready - sending initial `trigger` event")
            for trigger in trigger_events.values():
                trigger.set()
            break
        else:
            logger.trace("Waiting for all cameras to be ready...")
            time.sleep(1)

    while not exit_event.is_set():

        while not all([not trigger.is_set() for trigger in trigger_events.values()]):
            time.sleep(0.001)

        tik = time.perf_counter_ns()
        payload = trigger_multi_frame_read(frame_queues=frame_queues,
                                           multi_frame_pipe=multi_frame_pipe,
                                           config_update_pipe=config_update_pipe,
                                           payload=payload,
                                           trigger_events=trigger_events,
                                           config_update_queues=config_update_queues)
        payload = MultiFramePayload.from_previous(payload)
        check_loop_count(number_of_frames, payload, exit_event, tik)

    logger.debug(f"Closing camera trigger loop for cameras: {list(cameras.keys())}")


def trigger_multi_frame_read(frame_queues: Dict[CameraId, multiprocessing.Queue],
                             multi_frame_pipe,  # send-only pipe connection
                             config_update_pipe,  # receive-only pipe connection
                             config_update_queues: Dict[CameraId, multiprocessing.Queue],
                             payload: MultiFramePayload,
                             trigger_events: Dict[CameraId, multiprocessing.Event]) -> MultiFramePayload:
    for camera_id, trigger in trigger_events.items():
        if trigger.is_set():
            raise ValueError(f"Trigger is set for camera_id: {camera_id} - this should not happen!")
        trigger.set()

    payload = gather_incoming_frames(frame_queues=frame_queues,
                                     payload=payload,
                                     config_update_pipe=config_update_pipe,
                                     config_update_queues=config_update_queues,
                                     trigger_events=trigger_events)
    multi_frame_pipe.send(payload)
    logger.loop(f"Payload sent to multi_frame_pipe {[f'{camera_id}-{frame.image_shape}' for camera_id, frame in payload.frames.items()]}")
    return payload


def gather_incoming_frames(frame_queues: Dict[CameraId, multiprocessing.Queue],
                           payload: MultiFramePayload,
                           config_update_pipe,  # receive-only pipe connection
                           config_update_queues: Dict[CameraId, multiprocessing.Queue],
                           trigger_events: Dict[CameraId, multiprocessing.Event]) -> MultiFramePayload:
    all_frames_received = False
    while not all_frames_received:
        time.sleep(0.001)

        if all([not queue.empty() for queue in frame_queues.values()]):
            for camera_id, queue in frame_queues.items():
                frame = queue.get()
                if not isinstance(frame, FramePayload):
                    raise ValueError(f"Expected `FramePayload` but got {type(frame)}")

                payload.add_frame(frame)
            all_frames_received = True

        if config_update_pipe.poll():
            camera_configs = config_update_pipe.recv()
            for camera_id, update_queue in config_update_queues.items():
                update_queue.put(camera_configs[camera_id])
    return payload


def check_loop_count(number_of_frames: int,
                     payload: MultiFramePayload,
                     exit_event: multiprocessing.Event,
                     tik: int = None):
    log_loop_count(number_of_frames, payload, "completed", tik)

    if number_of_frames is not None:
        if payload.multi_frame_number + 1 >= number_of_frames:
            logger.trace(f"Reached number of frames: {number_of_frames} - setting `exit` event")
            exit_event.set()


def log_loop_count(number_of_frames: int, payload: MultiFramePayload, suffix: str, tik: int = None):
    loop_str = f"Loop# {payload.multi_frame_number}"
    if number_of_frames is not None and number_of_frames > 0:
        loop_str += f" of {number_of_frames} {suffix}"
    if tik is not None:
        elapsed = (time.perf_counter_ns() - tik) / 1e6
        loop_str += f" - (took {elapsed:.6f}ms)"
    logger.loop(loop_str)


def recreate_shared_memory_manager(camera_configs: CameraConfigs,
                                   shared_memory_name: str
                                   ) -> SharedPayloadMemoryManager:
    existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
    shared_memory_manager = SharedPayloadMemoryManager(camera_ids=list(camera_configs.keys()),
                                                       image_resolution=list(camera_configs.values())[0].resolution,
                                                       existing_shared_memory=existing_shared_memory)
    return shared_memory_manager
