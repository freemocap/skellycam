import multiprocessing
from typing import Optional

from skellycam.system.environment.get_logger import logger
from skellycam.backend.controller.core_functionality.camera_group.camera.internal_camera_thread import \
    VideoCaptureThread
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId


class Camera:
    def __init__(
            self,
            config: CameraConfig,
            pipe_sender_connection,  # multiprocessing.connection.Connection,
            is_capturing_event: multiprocessing.Event,
            all_cameras_ready_event: multiprocessing.Event,
            close_cameras_event: multiprocessing.Event,
    ):
        self._config = config
        self._pipe_sender_connection = pipe_sender_connection
        self._is_capturing_event = is_capturing_event
        self._all_cameras_ready_event = all_cameras_ready_event
        self._close_cameras_event = close_cameras_event

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
            is_capturing_event=self._is_capturing_event,
            all_cameras_ready_event=self._all_cameras_ready_event,
            close_cameras_event=self._close_cameras_event,
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
