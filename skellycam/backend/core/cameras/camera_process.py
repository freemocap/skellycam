import logging
import multiprocessing
import time
from multiprocessing import Process
from typing import List, Optional

import cv2
from setproctitle import setproctitle

from skellycam.backend.core.cameras.camera import (
    Camera,
)
from skellycam.backend.core.cameras.config.camera_config import CameraConfig
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.device_detection.image_rotation_types import RotationTypes
from skellycam.backend.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CameraProcess:
    def __init__(
            self,
            config: CameraConfig,
    ):

        self._camera_config = config
        self._process: Optional[Process] = None
        self._communication_queue = multiprocessing.Queue()
        self._receiver, self._sender = multiprocessing.Pipe(duplex=False)
        self._camera_running = multiprocessing.Value("b", False)

    @property
    def camera_running(self) -> bool:
        return self._camera_running.value

    @property
    def camera_id(self) -> CameraId:
        return self._camera_config.camera_id

    def update_config(self, camera_config: CameraConfig):
        self._communication_queue.put(camera_config)

    def start_capture(self):
        """
        Start capturing frames.
        :return:
        """
        logger.info(f"Starting capture `Process` for {self.camera_id}")

        self._process = Process(
            name=f"Camera {self.camera_id}",
            target=CameraProcess._run_process,
            args=(
                self._camera_config,
                self._sender,
                self._communication_queue,
            ),
        )
        self._process.start()
        self._wait_for_camera_to_start()
        logger.info(f"Capture `Process` for {self.camera_id} has started!")

    def _wait_for_camera_to_start(self):
        while not self._receiver.poll():
            logger.info(f"Waiting for camera {self.camera_id} to start...")
            time.sleep(1)
        logger.success(f"Camera {self.camera_id} ready!")
        self._camera_running.value = True

    def stop_capture(self):
        """
        Stop capturing frames. Only return if the underlying process is fully stopped.
        :return:
        """
        logger.info(f"Stopping capture `Process` for Camera {self.camera_id}")

        self._communication_queue.put(None)
        self._process.join()
        logger.info(f"Capture `Process` for {self.camera_id} has stopped")

    def get_new_frames(self) -> List[FramePayload]:

        if not self.camera_running:
            logger.trace(f"Camera {self.camera_id} is not ready yet - returning empty list.")
            return []

        logger.trace(f"Getting latest frames from camera {self.camera_id}")
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
            raise e
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
    ):
        logger.debug(
            f"Starting frame loop capture in CamGroupProcess for camera: {camera_config.camera_id}"
        )

        process_name = f"Camera {camera_config.camera_id}"
        setproctitle(process_name)

        camera = Camera(config=camera_config, frame_pipe=frame_pipe_sender, )
        camera.connect()

        while True:
            time.sleep(1.0)  # check for messages every second
            logger.trace(f"Checking camera {camera.camera_id} process communication queue...")
            if not communication_queue.empty():
                message = communication_queue.get()
                if message is None:
                    logger.info("Received None - closing cameras")
                    break
                elif isinstance(message, CameraConfig):
                    camera.update_config(message)
                else:
                    raise ValueError(f"Unknown message type: `{type(message)}` with value: '{message}'")

        logger.debug(f"Closing camera {camera.camera_id}")
        camera.close()

        logger.debug(f"CameraProcess - `{process_name}` - is complete")
