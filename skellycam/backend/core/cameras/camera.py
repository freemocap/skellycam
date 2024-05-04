import logging
from typing import Optional

from skellycam.backend.core.cameras.capture_thread import (
    CaptureThread,
)
from skellycam.backend.core.cameras.config.camera_config import CameraConfig
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class Camera:
    def __init__(
        self,
        config: CameraConfig,
        frame_pipe # multiprocessing.connection.Connection,
    ):
        self._config = config
        self._frame_pipe = frame_pipe

        self._capture_thread: Optional[CaptureThread] = None

    @property
    def camera_id(self) -> CameraId:
        return self._config.camera_id



    def connect(self):
        logger.info(f"Connecting to camera_id: {self.camera_id}")

        self._capture_thread = CaptureThread(
            config=self._config,
            frame_pipe=self._frame_pipe,
        )
        self._capture_thread.start()

    def close(self):
        self._capture_thread.stop()
        self._capture_thread.join()
        self._capture_thread = None
        logger.debug(f"Camera ID: [{self._config.camera_id}] has closed")

    def update_config(self, camera_config: CameraConfig, strict: bool = False) -> CameraConfig:
        logger.info(
            f"Updating config for camera_id: {self.camera_id}  ->  {camera_config}"
        )
        if not camera_config.use_this_camera:
            self.close()
        else:
            if not self._capture_thread:
                self.connect()

        return self._capture_thread.update_camera_config(new_config=camera_config,
                                                         strict=strict)
