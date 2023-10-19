import asyncio
import multiprocessing
import time
import traceback
from typing import Optional

from skellycam import logger
from skellycam.backend.controller.core_functionality.opencv.camera.internal_camera_thread import VideoCaptureThread
from skellycam.experiments.examples.viewers.cv_cam_viewer import CvCamViewer
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId


class Camera:
    def __init__(
            self,
            config: CameraConfig,
            pipe  # multiprocessing.connection.Connection,
    ):

        self._all_cameras_ready_event = None
        self._this_camera_ready_event = None
        self._config = config
        self._pipe = pipe
        self._capture_thread: Optional[VideoCaptureThread] = None

    @property
    def name(self):
        return f"Camera_{self._config.camera_id}"

    @property
    def camera_id(self) -> CameraId:
        return self._config.camera_id

    def connect(self,
                this_camera_ready: multiprocessing.Event,
                all_cameras_ready: multiprocessing.Event):

        self._this_camera_ready_event = this_camera_ready
        self._all_cameras_ready_event = all_cameras_ready

        if self._capture_thread and self._capture_thread.is_capturing_frames:
            logger.debug(f"Already capturing frames for camera_id: {self.camera_id}")
            return
        logger.debug(f"Camera ID: [{self._config.camera_id}] Creating thread")
        self._capture_thread = VideoCaptureThread(
            config=self._config,
            pipe=self._pipe,
            this_camera_ready_event=self._this_camera_ready_event,
            all_cameras_ready_event=all_cameras_ready,
        )
        self._capture_thread.start()

    def stop_frame_capture(self):
        self._capture_thread.stop()

    def close(self):
        try:
            self._capture_thread.stop()
            while self._capture_thread.is_alive():
                # wait for thread to die.
                # TODO: use threading.Event for synchronize mainthread vs other threads
                time.sleep(0.1)
        except:
            logger.error("Printing traceback")
            traceback.print_exc()
        finally:
            logger.info(f"Camera ID: [{self._config.camera_id}] has closed")

    def update_config(self, camera_config: CameraConfig):
        logger.info(
            f"Updating config for camera_id: {self.camera_id}  -  {camera_config}"
        )
        if not camera_config.use_this_camera:
            self.close()
        else:
            if not self._capture_thread.is_capturing_frames:
                self.connect(this_camera_ready=self._this_camera_ready_event,
                             all_cameras_ready=self._all_cameras_ready_event)

            self._capture_thread.update_camera_config(camera_config)
