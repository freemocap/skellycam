import asyncio
import logging
import multiprocessing
import time
import traceback
from typing import Optional

from skellycam.opencv.camera.attributes import Attributes
from skellycam.opencv.camera.config.camera_config import CameraConfig
from skellycam.opencv.camera.internal_camera_thread import VideoCaptureThread

from skellycam.viewers.cv_cam_viewer import CvCamViewer

logger = logging.getLogger(__name__)


class Camera:
    def __init__(
        self,
        config: CameraConfig,
    ):
        self._ready_event = None
        self._config = config
        self._capture_thread: Optional[VideoCaptureThread] = None

    @property
    def name(self):
        return f"Camera_{self._config.camera_id}"

    @property
    def attributes(self):
        return Attributes(self._capture_thread)

    @property
    def camera_id(self):
        return str(self._config.camera_id)

    @property
    def is_capturing_frames(self):
        return self._capture_thread.is_capturing_frames

    @property
    def new_frame_ready(self):
        return self._capture_thread.new_frame_ready

    @property
    def latest_frame(self):
        return self._capture_thread.latest_frame

    def wait_for_next_frame(self):
        while True:
            if not self.new_frame_ready:
                time.sleep(0.001)
            return self.latest_frame

    def connect(self, wait_for_capture: bool = False):
        if self._capture_thread and self._capture_thread.is_capturing_frames:
            logger.debug(f"Already capturing frames for camera_id: {self.camera_id}")
            return

        logger.debug(f"Camera ID: [{self._config.camera_id}] Creating thread")
        self._capture_thread = VideoCaptureThread(config=self._config)
        self._capture_thread.start()
        if not wait_for_capture:
            return

        # connect may wait for the thread to grab frames.
        while (
            self._capture_thread.is_alive()
            and not self._capture_thread.is_capturing_frames
        ):
            time.sleep(0.1)

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

    async def show_async(self):
        viewer = CvCamViewer()
        viewer.begin_viewer(self.camera_id)
        while True:
            if self.new_frame_ready:
                viewer.recv_img(self.latest_frame)
                await asyncio.sleep(0)

    def show(self):
        viewer = CvCamViewer()
        viewer.begin_viewer(self.camera_id)
        while True:
            if self.new_frame_ready:
                viewer.recv_img(self.latest_frame)

    def update_config(self, camera_config: CameraConfig):
        logger.info(
            f"Updating config for camera_id: {self.camera_id}  -  {camera_config}"
        )
        if not camera_config.use_this_camera:
            self.close()
            return

        if camera_config.use_this_camera and not self._capture_thread.is_alive():
            self.connect()

        self._capture_thread.update_camera_config(camera_config)
