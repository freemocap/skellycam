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
    tasks = {camera_id: trigger_camera_factory(config) for camera_id, config in camera_configs.items()}
    cameras = await asyncio.gather(*tasks.values())
    return dict(zip(tasks.keys(), cameras))


async def trigger_camera_read(cameras: [CameraId, TriggerCamera], payload: MultiFramePayload) -> MultiFramePayload:
    tasks = {camera_id: camera.get_frame for camera_id, camera in cameras}
    frames = await asyncio.gather(*tasks.values())
    for camera_id, frame in zip(tasks.keys(), frames):
        payload[camera_id] = frame
    return payload


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
    def camera_ids(self):
        return self._camera_configs.keys()

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

        payload: Optional[MultiFramePayload] = None
        while True:
            if payload is None:
                payload = MultiFramePayload.create(list(cameras.keys()))
            payload = asyncio.run(trigger_camera_read(cameras, payload))

            if not communication_queue.empty():
                message = communication_queue.get()
                if message is None:
                    logger.debug("Recieved `None` - breaking frame loop")
                    break
                elif isinstance(message, CameraConfigs):
                    logger.debug("Updating camera configs")
                    asyncio.run(update_camera_configs(cameras, message))
                    payload.log("update_camera_configs")

            frame_pipe.send_bytes(payload.to_msgpack())
