import logging
import pprint
import threading
import time
from typing import Optional

import cv2

from skellycam.backend.core.camera.config.apply_config import (
    apply_camera_configuration,
)
from skellycam.backend.core.camera.config.camera_config import CameraConfig
from skellycam.backend.core.camera.config.determine_backend import determine_backend
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class FailedToReadFrameFromCameraException(Exception):
    pass


class FailedToOpenCameraException(Exception):
    pass


class FrameCaptureThread(threading.Thread):
    def __init__(
            self,
            config: CameraConfig,
            frame_pipe,  # multiprocessing.connection.Connection
    ):
        super().__init__()
        self._config = config
        self.frame_pipe = frame_pipe

        self.daemon = True
        self._cv2_video_capture = None
        self._updating_config = False
        self._should_continue = True

    def run(self):
        self._cv2_video_capture = self._create_cv2_capture()
        self.update_camera_config(self._config)
        self._start_frame_loop()

    def stop(self):
        logger.debug("Stopping frame capture loop...")
        self._should_continue = False
        if self._cv2_video_capture is not None:
            self._cv2_video_capture.release()

    def update_camera_config(self, new_config: CameraConfig):
        self._updating_config = True
        self._config = new_config
        logger.info(f"Updating Camera: {self._config.camera_id} config to {new_config}")
        apply_camera_configuration(self._cv2_video_capture, new_config)
        self._updating_config = False

    def _create_cv2_capture(self):
        cap_backend = determine_backend()
        logger.info(
            f"Creating cv.VideoCapture object for Camera: {self._config.camera_id} "
            f"using backend `{cap_backend.name}`..."
        )

        capture = cv2.VideoCapture(int(self._config.camera_id), cap_backend.value)
        if not capture.isOpened():
            raise FailedToOpenCameraException(
                f"Failed to open camera with config: {pprint.pformat(self._config)}"
            )
        success, image = capture.read()

        if not success or image is None:
            raise FailedToReadFrameFromCameraException(
                f"Failed to read frame from camera with config: {pprint.pformat(self._config)} "
                f"returned value: {success}, "
                f"returned image: {image}"
            )

        logger.info(f"Successfully connected to Camera: {self._config.camera_id}!")
        return capture

    def _start_frame_loop(self):
        logger.info(
            f"Camera ID: [{self._config.camera_id}] starting frame capture loop..."
        )
        self._frame_number = -1
        self._frame_loop()  # main frame loop

    def _frame_loop(self):
        """
        This loop is responsible for capturing frames from the camera and stuffing them into the pipe
        """
        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop is running"
        )
        try:
            while self._should_continue:
                if self._updating_config:
                    time.sleep(0.001)
                    continue

                frame = self._get_next_frame()

                if frame is None:
                    time.sleep(0.001)
                    continue
                else:
                    self.frame_pipe.send_bytes(frame.to_msgpack())

        except Exception as e:
            logger.error(f"Error in frame capture loop: {e}")
            logger.exception(e)
            raise e
        finally:
            self.stop()
            logger.info(
                f"Camera ID: [{self._config.camera_id}] Frame capture loop has stopped"
            )

    def _get_next_frame(self) -> Optional[FramePayload]:
        """
        THIS IS WHERE THE MAGIC HAPPENS

        This method is responsible for grabbing the next frame from the camera - it is the point of "transduction"
         when a pattern of environmental energy (i.e. a timeslice of the 2D pattern of light intensity in 3 wavelengths
          within the field of view of the camera ) is absorbed by the camera's sensor and converted into a digital
          representation of that pattern (i.e. a 2D array of pixel values in 3 channels).

        This is the empirical measurement, whereupon all future inference will derive their epistemological grounding.

        This sweet baby must be protected at all costs. Nothing is allowed to block this call (which could result in
        a frame drop)
        """

        success, image = self._cv2_video_capture.read()  # THIS IS WHERE THE MAGIC HAPPENS <3

        if not success or image is None:
            logger.warning(f"Failed to read frame from camera: {self._config.camera_id}")
            return

        retrieval_timestamp = time.perf_counter_ns()
        self._frame_number += 1
        return FramePayload.create(
            success=success,
            image=image,
            timestamp_ns=retrieval_timestamp,
            frame_number=self._frame_number,
            camera_id=CameraId(self._config.camera_id),
        )