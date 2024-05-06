import asyncio
import logging
import multiprocessing
import time
from multiprocessing import Process
from typing import List, Optional

import cv2
from pydantic import BaseModel, Field
from setproctitle import setproctitle

from skellycam.core.cameras.thread_loop_camera.loop_camera import (
    LoopCamera,
)
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.device_detection.camera_id import CameraId
from skellycam.core.device_detection.image_rotation_types import RotationTypes
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class UpdateConfigMessage(BaseModel):
    camera_config: CameraConfig
    strict: bool = Field(default=False,
                         description="If True, will raise an error if the camera settings do not match the target config after updating.")


class CameraLoopProcess:
    def __init__(
            self,
            config: CameraConfig,
    ):
        self._camera_config = config
        self._process: Optional[Process] = None
        self._communication_queue = multiprocessing.Queue()
        self._receiver, self._sender = multiprocessing.Pipe(duplex=False)
        self._camera_ready_event = multiprocessing.Event()
        self._camera_should_start_event = multiprocessing.Event()

    @property
    def camera_id(self) -> CameraId:
        return self._camera_config.camera_id

    async def update_config(self, camera_config: CameraConfig, strict: bool = False):
        logger.debug(f"Updating camera config for {self.camera_id} to {camera_config}")
        self._communication_queue.put(UpdateConfigMessage(camera_config=camera_config,
                                                          strict=strict))
        while True:
            if self._communication_queue.empty():
                await asyncio.sleep(0.1)
            else:
                message = self._communication_queue.get()
                logger.debug(f"Response from camera {self.camera_id}: {message}")

    def start_capturing(self):
        self._communication_queue.put("start")

    async def start_process(self):
        logger.debug(f"Starting capture `Process` for {self.camera_id}")

        self._process = Process(
            name=f"Camera-{self.camera_id}",
            target=CameraLoopProcess._run_process,
            args=(
                self._camera_config,
                self._sender,
                self._communication_queue,
                self._camera_ready_event,
                self._camera_should_start_event,
            ),
        )
        self._process.start()
        await self._wait_for_camera_ready()
        logger.info(f"Capture `Process` for {self.camera_id} ready!")

    def start_capture(self):
        logger.debug(f"Starting capture for camera {self.camera_id}")
        self._camera_should_start_event.set()

    async def _wait_for_camera_ready(self):
        while not self._camera_ready_event.is_set():
            await asyncio.sleep(1.0)

    def stop_capture(self):
        """
        Stop capturing frames. Only return if the underlying process is fully stopped.
        :return:
        """
        if self._process is None:
            logger.debug(f"Camera {self.camera_id} not running - nothing to stop")
            return

        logger.info(f"Stopping capture `Process` for Camera {self.camera_id}")

        self._communication_queue.put(None)
        self._process.join()
        logger.info(f"Capture `Process` for {self.camera_id} has stopped")

    def get_new_frames(self) -> List[FramePayload]:
        new_frames = []
        try:
            while self._receiver.poll():
                frame_msgpack = self._receiver.recv_bytes()
                frame = FramePayload.from_msgpack(frame_msgpack)
                new_frames.append(frame)

            if len(new_frames) > 0:
                self._apply_image_rotation(new_frames)

        except Exception as e:
            logger.error(
                f"Problem when grabbing a frame from: Camera {self.camera_id} - {type(e).__name__} : {e}"
            )
            logger.exception(e)
            raise
        return new_frames

    def _apply_image_rotation(self, new_frames: List[FramePayload]):
        for frame in new_frames:
            if self._camera_config.rotation != RotationTypes.NO_ROTATION:
                frame.image = cv2.rotate(frame.image, self._camera_config.rotation.to_opencv_constant())

    @staticmethod
    def _run_process(
            camera_config: CameraConfig,
            frame_pipe_sender,  # multiprocessing.connection.Connection
            communication_queue: multiprocessing.Queue,
            camera_ready_event: multiprocessing.Event,
            camera_should_start_event: multiprocessing.Event,
    ):
        logger.debug(
            f"Starting frame loop capture in CamGroupProcess for camera: {camera_config.camera_id}"
        )

        process_name = f"Camera {camera_config.camera_id}"
        setproctitle(process_name)

        camera = LoopCamera(config=camera_config, frame_pipe=frame_pipe_sender)
        camera.connect()
        camera_ready_event.set()
        logger.debug(f"Camera {camera_config.camera_id} ready - awaiting start signal")
        while True:
            if camera_should_start_event.is_set():
                break
            time.sleep(0.001)
        logger.debug(f"Camera {camera_config.camera_id} capture started!")

        while True:
            time.sleep(1.0)  # check for messages every second
            if not communication_queue.empty():
                message = communication_queue.get()
                if message is None:
                    logger.info("Received None - closing cameras")
                    break
                elif isinstance(message, UpdateConfigMessage):
                    if message.camera_config == camera_config:
                        communication_queue.put(f"Camera {camera.camera_id} config matches current config - skipping")
                    else:
                        logger.debug(f"Updating camera {camera.camera_id} config to {message}")
                        camera.update_config(message.camera_config, strict=message.strict)
                        communication_queue.put(f"Camera {camera.camera_id} config updated")
                else:
                    raise ValueError(f"Unknown message type: `{type(message)}` with value: '{message}'")

        logger.debug(f"Closing camera {camera.camera_id}")
        camera.close()

        logger.debug(f"CameraProcess - `{process_name}` - is complete")
