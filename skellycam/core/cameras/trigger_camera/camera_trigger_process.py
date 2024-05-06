import asyncio
import logging
import multiprocessing
import threading
import time
from multiprocessing import Process, shared_memory
from typing import Dict, Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.trigger_camera.trigger_camera import TriggerCamera
from skellycam.core.device_detection.camera_id import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.shared_image_memory import SharedImageMemoryManager

logger = logging.getLogger(__name__)


async def trigger_camera_factory(config) -> TriggerCamera:
    camera = TriggerCamera()
    await camera.start(config)
    return camera


async def start_cameras(camera_configs: CameraConfigs) -> Dict[CameraId, TriggerCamera]:
    logger.info(f"Starting cameras: {list(camera_configs.keys())}")
    tasks = {camera_id: trigger_camera_factory(config) for camera_id, config in camera_configs.items()}
    results = await asyncio.gather(*tasks.values())
    cameras = dict(zip(tasks.keys(), results))
    for camera_id, camera in cameras.items():
        if not camera.is_connected:
            raise Exception(f"Failed to connect to camera {camera_id}")
    logger.success(f"All cameras connected: {list(cameras.keys())}")
    return cameras


async def trigger_camera_read(cameras: Dict[CameraId, TriggerCamera],
                              payload: MultiFramePayload,
                              shared_memory_manager: SharedImageMemoryManager,
                              ) -> MultiFramePayload:
    logger.loop(f"Triggering camera read...")
    get_frame_tasks = [camera.get_frame() for camera in cameras.values()]
    frames = await asyncio.gather(*get_frame_tasks)
    add_frame_tasks = []
    for camera_id, frame in zip(cameras.keys(), frames):
        if frame is None:
            continue
        if not isinstance(frame, FramePayload):
            logger.error(f"Received unexpected frame type: {type(frame)}")
            continue
        add_frame_tasks = [payload.add_shared_memory_image(frame,
                                                           shared_memory_manager)]
    await asyncio.gather(*add_frame_tasks)
    logger.loop(f"Received multi-frame payload from Cameras {list(payload.camera_ids)}")
    return payload


async def check_communication_queue(cameras: Dict[CameraId, TriggerCamera],
                                    aqueue: asyncio.Queue,
                                    exit_event: asyncio.Event):
    if not aqueue.empty():
        message = await aqueue.get()
        if message is None:
            logger.debug("Received `None` - setting `exit` event")
            exit_event.set()
            logger.debug("Closing cameras...")
            close_tasks = [camera.close() for camera in cameras.values()]
            await asyncio.gather(*close_tasks)
            logger.debug("Cameras closed")
        elif isinstance(message, CameraConfigs):
            logger.debug("Received CameraConfigs - updating camera configs")
            await update_camera_configs(cameras, message)
            logger.debug("Camera configs updated")


async def camera_trigger_loop(camera_configs: CameraConfigs,
                              aqueue: asyncio.Queue,
                              shared_memory_manager: SharedImageMemoryManager,
                              exit_event: asyncio.Event,
                              number_of_frames: Optional[int] = None,
                              ):
    cameras = await start_cameras(camera_configs)

    logger.info(f"Camera trigger loop started!")
    payload = MultiFramePayload.create()

    while not exit_event.is_set():
        payload = await trigger_camera_read(cameras, payload, shared_memory_manager)
        await log_loop_count(number_of_frames, payload, "started")
        aqueue.put_nowait(payload)
        payload = MultiFramePayload.from_previous(payload)
        await check_communication_queue(cameras, aqueue, exit_event)
        await check_loop_count(number_of_frames, payload, exit_event)

    logger.debug("Camera trigger loop complete")


async def check_loop_count(number_of_frames: int, payload: MultiFramePayload, exit_event: asyncio.Event):
    log_loop_count(number_of_frames, payload, "completed")

    if number_of_frames is not None:
        if payload.multi_frame_number >= number_of_frames:
            logger.debug(f"Reached number of frames: {number_of_frames} - setting `exit` event")
            exit_event.set()


async def log_loop_count(number_of_frames: int, payload: MultiFramePayload, suffix: str):
    loop_str = f"Loop#{payload.multi_frame_number}"
    if number_of_frames is not None and number_of_frames > 0:
        loop_str += f" of {number_of_frames} {suffix}"
    logger.loop(loop_str)


async def update_camera_configs(cameras: [CameraId, TriggerCamera], configs: CameraConfigs):
    tasks = []
    for camera, config in zip(cameras.values(), configs.values()):
        tasks.append(camera.update_config(config))
    await asyncio.gather(*tasks)


class CameraTriggerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            frame_pipe,  # send-only pipe connection
            shared_memory_name: str
    ):
        self._camera_configs = camera_configs
        self._frame_pipe = frame_pipe
        self._shared_memory_name = shared_memory_name
        self._communication_queue = multiprocessing.Queue()
        self._number_of_frames: Optional[int] = None
        self._process: Optional[Process] = None

    def _create_process(self):
        self._process = Process(
            name="CameraTriggerProcess",
            target=CameraTriggerProcess._run_process,
            args=(self._camera_configs,
                  self._frame_pipe,
                  self._communication_queue,
                  self._shared_memory_name,
                  self._number_of_frames
                  )
        )

    @property
    def camera_ids(self) -> [CameraId]:
        return list(self._camera_configs.keys())

    def start(self, number_of_frames: Optional[int] = None):
        logger.debug("Stating CameraTriggerProcess...")
        self._number_of_frames = number_of_frames
        self._create_process()
        self._process.start()

    def update_configs(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._communication_queue.put(camera_configs)

    async def close(self):
        logger.debug("Closing CameraTriggerProcess...")
        self._communication_queue.put(None)
        self._process.join()
        logger.debug("CameraTriggerProcess closed")

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     frame_pipe,  # send-only pipe connection
                     communication_queue: multiprocessing.Queue,
                     shared_memory_name: str,
                     number_of_frames: Optional[int] = None
                     ):
        logger.debug(f"CameraTriggerProcess started")
        exit_event = asyncio.Event()
        async_queue = asyncio.Queue()
        existing_shared_memory = shared_memory.SharedMemory(name=shared_memory_name)
        shared_memory_manager = SharedImageMemoryManager(list(camera_configs.values())[0].resolution,
                                                         existing_shared_memory=existing_shared_memory)
        relay_thread = threading.Thread(target=CameraTriggerProcess._relay_thread,
                                        args=(async_queue, communication_queue, frame_pipe, exit_event))
        relay_thread.start()
        try:
            asyncio.run(camera_trigger_loop(camera_configs=camera_configs,
                                            aqueue=async_queue,
                                            shared_memory_manager=shared_memory_manager,
                                            number_of_frames=number_of_frames,
                                            exit_event=exit_event))
        except Exception as e:
            logger.error(f"Erorr in CameraTriggerProcess: {type(e).__name__} - {e}")
            raise
        logger.debug(f"CameraTriggerProcess complete")

    @staticmethod
    def _relay_thread(aqueue: asyncio.Queue,
                      communication_queue: multiprocessing.Queue,
                      frame_pipe,  # send-only pipe connection
                      exit_event: asyncio.Event):
        logger.trace("Relay thread started")
        while not exit_event.is_set():
            if not communication_queue.empty():
                message = communication_queue.get()
                logger.trace(f"Relay thread received message: {message}, relay to asyncio queue")
                aqueue.put_nowait(message)

            if not aqueue.empty():
                message = aqueue.get_nowait()
                if isinstance(message, MultiFramePayload):
                    logger.trace(f"Relay thread received MultiFramePayload, sending to frame_pipe")
                    frame_pipe.send(message)
            time.sleep(0.001)

        logger.debug("Relay thread complete")
