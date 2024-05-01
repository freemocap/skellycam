import logging
import multiprocessing
from typing import Optional

from skellycam.backend.core.camera.internal_camera_thread import (
    VideoCaptureThread,
)
from skellycam.backend.core.camera.config.camera_config import CameraConfig
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class Camera:
    def __init__(
        self,
        config: CameraConfig,
        pipe_sender_connection,  # multiprocessing.connection.Connection,
    ):
        self._config = config
        self._pipe_sender_connection = pipe_sender_connection

        self._capture_thread: Optional[VideoCaptureThread] = None

    @property
    def camera_id(self) -> CameraId:
        return self._config.camera_id

    def connect(self):
        if self._capture_thread and self._capture_thread.is_capturing_frames:
            logger.debug(f"Already capturing frames for camera_id: {self.camera_id}")
            return
        logger.debug(f"Camera ID: [{self._config.camera_id}] Creating thread")
        self._capture_thread = VideoCaptureThread(
            config=self._config,
            pipe_sender_connection=self._pipe_sender_connection,
        )
        self._capture_thread.start()

    def close(self):
        self._capture_thread.stop()
        self._capture_thread.join()
        logger.debug(f"Camera ID: [{self._config.camera_id}] has closed")

    def update_config(self, camera_config: CameraConfig):
        logger.info(
            f"Updating config for camera_id: {self.camera_id}  -  {camera_config}"
        )
        if not camera_config.use_this_camera:
            self.close()
        else:
            if not self._capture_thread.is_capturing_frames:
                self.connect()

            self._capture_thread.update_camera_config(camera_config)
