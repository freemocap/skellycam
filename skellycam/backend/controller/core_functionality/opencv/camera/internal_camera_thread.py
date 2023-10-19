import multiprocessing
import pprint
import threading
import time

import cv2

from skellycam import logger
from skellycam.backend.controller.core_functionality.config.apply_config import apply_camera_configuration
from skellycam.backend.controller.core_functionality.config.determine_backend import determine_backend
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frame_models.frame_payload import FramePayload


class FailedToReadFrameFromCameraException(Exception):
    pass


class VideoCaptureThread(threading.Thread):
    def __init__(
            self,
            config: CameraConfig,
            ready_event: multiprocessing.Event = None,
    ):
        super().__init__()
        self._previous_frame_timestamp_ns = None
        self._new_frame_ready = False
        self.daemon = False

        if ready_event is None:
            self._ready_event = multiprocessing.Event()
            self._ready_event.set()
        else:
            self._ready_event = ready_event

        self._config = config
        self._is_capturing_frames = False

        self._number_of_frames_received: int = 0

        self._frame: FramePayload = FramePayload()
        self._cv2_video_capture = None

    @property
    def latest_frame(self) -> FramePayload:
        self._new_frame_ready = False
        return self._frame

    @property
    def new_frame_ready(self):
        return self._new_frame_ready

    @property
    def is_capturing_frames(self) -> bool:
        return self._is_capturing_frames

    def run(self):
        self._cv2_video_capture = self._create_cv2_capture()
        self._start_frame_loop()

    def _start_frame_loop(self):
        self._is_capturing_frames = True
        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has started"
        )

        while self._is_capturing_frames:
            self._frame = self._get_next_frame()

        self._cv2_video_capture.release()
        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has exited"
        )

    def _get_next_frame(self):
        success, image = self._cv2_video_capture.read()
        retrieval_timestamp = time.perf_counter_ns()
        self._new_frame_ready = success
        if success:
            self._number_of_frames_received += 1
        else:
            raise FailedToReadFrameFromCameraException(
                f"Failed to read frame from camera with config: {pprint.pformat(self._config)} "
                f"returned value: {success}, "
                f"returned image: {image}"
            )
        return FramePayload(
            success=success,
            image=image,
            timestamp_ns=retrieval_timestamp,
            number_of_frames_received=self._number_of_frames_received,
            camera_id=str(self._config.camera_id),
        )

    def _create_cv2_capture(self):
        logger.info(f"Connecting to Camera: {self._config.camera_id}...")
        cap_backend = determine_backend()

        if self._cv2_video_capture is not None and self._cv2_video_capture.isOpened():
            self._cv2_video_capture.release()

        capture = cv2.VideoCapture(int(self._config.camera_id), cap_backend)
        apply_camera_configuration(capture, self._config)

        success, image = capture.read()

        if not success or image is None:
            raise FailedToReadFrameFromCameraException(
                f"Failed to read frame from camera with config: {pprint.pformat(self._config)} "
                f"returned value: {success}, "
                f"returned image: {image}"
            )

        logger.success(f"Successfully connected to Camera: {self._config.camera_id}!")
        if not self._ready_event.is_set():
            self._ready_event.set()

        return capture

    def stop(self):
        logger.debug("Stopping frame capture loop...")
        self._is_capturing_frames = False
        if self._cv2_video_capture is not None and self._cv2_video_capture.isOpened():
            self._cv2_video_capture.release()

    def update_camera_config(self, new_config: CameraConfig):
        self._config = new_config
        logger.info(f"Updating Camera: {self._config.camera_id} config to {new_config}")
        apply_camera_configuration(self._cv2_video_capture, new_config)

