import asyncio
import logging
import multiprocessing
from multiprocessing import Process
from typing import Optional, Dict

from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.cameras.trigger_camera.trigger_camera import TriggerCamera
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


async def trigger_camera_factory(config) -> TriggerCamera:
    camera = TriggerCamera(config)
    await camera.connect()
    return camera


async def connect_cameras(camera_configs: CameraConfigs) -> Dict[CameraId, TriggerCamera]:
    logger.debug(f"Connecting cameras: {camera_configs}")
    tasks = {camera_id: trigger_camera_factory(config) for camera_id, config in camera_configs.items()}
    results = await asyncio.gather(*tasks.values())
    cameras = dict(zip(tasks.keys(), results))
    logger.debug(f"Connected cameras: {cameras.keys()}")
    return cameras


async def trigger_camera_read(cameras: Dict[CameraId, TriggerCamera],
                              payload: MultiFramePayload) -> MultiFramePayload:
    logger.loop("Triggering camera read...")
    tasks = [camera.get_frame() for camera in cameras.values()]
    frames = await asyncio.gather(*tasks)
    for camera_id, frame in zip(cameras.keys(), frames):
        payload[camera_id] = frame
    logger.loop(f"Trigger returned - {payload}")
    return payload


async def communication_queue_loop(cameras: Dict[CameraId, TriggerCamera],
                                    communication_queue: multiprocessing.Queue,
                                    exit_event: asyncio.Event):
    logger.debug("Starting communication queue loop")
    while not exit_event.is_set():
        if not communication_queue.empty():
            message = communication_queue.get()
            if message is None:
                logger.debug("Received `None` - setting `exit` event")
                exit_event.set()
            elif isinstance(message, CameraConfigs):
                logger.debug("Updating camera configs")
                await update_camera_configs(cameras, message)
    logger.debug("Communication queue loop complete")


async def camera_trigger_loop(cameras: Dict[CameraId, TriggerCamera],
                              frame_pipe,  # send-only pipe connection
                              communication_queue: multiprocessing.Queue,
                              exit_event: asyncio.Event):
    payload = MultiFramePayload.create(list(cameras.keys()))
    communication_queue_task = asyncio.create_task(communication_queue_loop(cameras, communication_queue, exit_event))
    while not exit_event.is_set():

        payload = await trigger_camera_read(cameras, payload)

        logger.loop(f"Sending payload: {payload}")
        payload.log("before_putting_in_pipe_from_trigger_loop")
        frame_pipe.send_bytes(payload.to_msgpack())
        payload = MultiFramePayload.from_previous(payload)
        frame_pipe.send_bytes(payload.to_msgpack())

    if not communication_queue_task.done():
        communication_queue.put(None)
        await communication_queue_task


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
    ):
        self._camera_configs = camera_configs
        self._communication_queue = multiprocessing.Queue()
        self._process = Process(
            name="CameraTriggerProcess",
            target=CameraTriggerProcess._run_process,
            args=(self._camera_configs,
                  frame_pipe,
                  self._communication_queue,
                  )
        )

    @property
    def camera_ids(self) -> [CameraId]:
        return list(self._camera_configs.keys())

    def start(self):
        logger.debug("Stating CameraTriggerProcess...")
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
                     communication_queue: multiprocessing.Queue):
        logger.debug(f"Starting Camera Trigger Process")

        cameras = asyncio.run(connect_cameras(camera_configs))
        exit_event = asyncio.Event()
        payload: Optional[MultiFramePayload] = None
        while True:
            if payload is None:
                payload = MultiFramePayload.create(list(cameras.keys()))
            payload = asyncio.run(trigger_camera_read(cameras, payload))

            asyncio.run(camera_trigger_loop(cameras, frame_pipe, communication_queue, exit_event))
