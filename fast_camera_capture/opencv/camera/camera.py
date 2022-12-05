import asyncio
import logging
import time
import traceback
from typing import Optional, Union

from fast_camera_capture.opencv.camera.models.cam_args import CamArgs
from fast_camera_capture.opencv.camera.attributes import Attributes
from fast_camera_capture.opencv.camera.internal_camera_thread import VideoCaptureThread
from fast_camera_capture.opencv.viewer.cv_imshow.cv_cam_viewer import CvCamViewer

logger = logging.getLogger(__name__)


class Camera:
    def __init__(
        self,
        config: CamArgs,
    ):
        self._config = config
        self._capture_thread: Optional[VideoCaptureThread] = None

    @property
    def name(self):
        return f"Camera_{self._config.cam_id}"

    @property
    def attributes(self):
        return Attributes(self._capture_thread)

    @property
    def cam_id(self):
        return str(self._config.cam_id)

    @property
    def is_capturing_frames(self):
        return self._capture_thread.is_capturing_frames

    @property
    def new_frame_ready(self):
        return self._capture_thread.new_frame_ready

    @property
    def latest_frame(self):
        return self._capture_thread.latest_frame

    def connect(self):
        if self._capture_thread and self._capture_thread.is_capturing_frames:
            logger.debug(f"Already capturing frames for webcam_id: {self.cam_id}")
            return
        logger.debug(f"Camera ID: [{self._config.cam_id}] Creating thread")
        self._capture_thread = VideoCaptureThread(
            config=self._config,
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
            logger.info(f"Camera ID: [{self._config.cam_id}] has closed")

    async def show_async(self):
        viewer = CvCamViewer()
        viewer.begin_viewer(self.cam_id)
        while True:
            if self.new_frame_ready:
                viewer.recv_img(self.latest_frame)
                await asyncio.sleep(0)

    def show(self):
        viewer = CvCamViewer()
        viewer.begin_viewer(self.cam_id)
        while True:
            if self.new_frame_ready:
                viewer.recv_img(self.latest_frame)
