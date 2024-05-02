import logging
import multiprocessing
import time
from multiprocessing import Process
from typing import List, Optional

import cv2
from setproctitle import setproctitle

from skellycam.backend.core.camera.camera import (
    Camera,
)
from skellycam.backend.core.camera.config.camera_config import CameraConfig
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

    @property
    def camera_id(self) -> CameraId:
        return self._camera_config.camera_id

    def update_config(self, camera_config: CameraConfig):
        self._communication_queue.put(camera_config)

    def start_capture(self):
        """
        Start capturing frames. Only return if the underlying process is fully running.
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
        new_frames = []
        try:
            while self._receiver.poll():
                frame_msgpack = self._receiver.recv_bytes()
                new_frames.append(FramePayload.from_msgpack(frame_msgpack))

            if len(new_frames) > 0:
                self._apply_image_rotation(new_frames)

        except Exception as e:
            logger.error(
                f"Problem when grabbing a frame from: Camera {self.camera_id} - {e}"
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
            # logger.trace(f"CamGroupProcess {process_name} is checking for new configs")
            time.sleep(1.0)  # check for new configs every so often
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