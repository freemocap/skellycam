import multiprocessing
import pprint
import threading
import time

import cv2

from skellycam import logger
from skellycam.backend.controller.core_functionality.config.apply_config import apply_camera_configuration
from skellycam.backend.controller.core_functionality.config.determine_backend import determine_backend
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frames.frame_payload import FramePayload


class FailedToReadFrameFromCameraException(Exception):
    pass


class VideoCaptureThread(threading.Thread):
    def __init__(
            self,
            config: CameraConfig,
            pipe,  # multiprocessing.connection.Connection
            is_capturing_event: multiprocessing.Event,
            all_cameras_ready_event: multiprocessing.Event,
    ):
        super().__init__()
        self._should_run_frame_loop = False
        self._pipe = pipe
        self.daemon = True
        self._is_capturing_event = is_capturing_event
        self._all_cameras_ready_event = all_cameras_ready_event
        self._config = config
        self._cv2_video_capture = None

    @property
    def is_capturing_frames(self) -> bool:
        return self._is_capturing_event.is_set()

    def run(self):
        self._cv2_video_capture = self._create_cv2_capture()
        self._start_frame_loop()

    def _start_frame_loop(self):

        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has started"
        )
        self._wait_for_all_cameras_ready()
        self._frame_number = -1

        self._frame_loop()  # main frame loop

        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has exited"
        )

    def _frame_loop(self):
        """
        This loop is responsible for capturing frames from the camera and stuffing them into the pipe
        """
        self._is_capturing_event.set()
        try:
            while self._should_run_frame_loop:
                frame = self._get_next_frame()
                self._pipe.send_bytes(frame.to_bytes())
        except Exception as e:
            logger.error(f"Error in frame capture loop: {e}")
            logger.exception(e)
            raise e

    def _get_next_frame(self) -> FramePayload:
        """
        THIS IS WHERE THE MAGIC HAPPENS

        This method is responsible for grabbing the next frame from the camera - it is the point of "transduction"
         when a pattern of environmental energy (i.e. a timeslice of the 2D pattern of light intensity in 3 wavelengths
          within the field of view of the camera ) is abosrbed by the camera's sensor and converted into a digital
          representation of that pattern (i.e. a 2D array of pixel values in 3 channels).

        This is the empirical measurement, whereupon all future inference will derive their empirical grounding.

        This sweet baby must be protected at all costs. Nothing is allowed to block this call (which could result in
        a frame drop)
        """

        success, image = self._cv2_video_capture.read()  #THIS IS WHERE THE MAGIC HAPPENS
        retrieval_timestamp = time.perf_counter()
        self._frame_number += 1
        return FramePayload.create(
            success=success,
            image=image,
            timestamp_ns=int(retrieval_timestamp),
            frame_number=self._frame_number,
            camera_id=self._config.camera_id,
        )

    def _wait_for_all_cameras_ready(self):
        while not self._all_cameras_ready_event.is_set():
            time.sleep(.001)
            continue
        self._should_run_frame_loop = True

    def _create_cv2_capture(self):
        logger.info(f"Connecting to Camera: {self._config.camera_id}...")
        cap_backend = determine_backend()

        if self._cv2_video_capture is not None and self._cv2_video_capture.isOpened():
            self._cv2_video_capture.release()

        capture = cv2.VideoCapture(self._config.camera_id, cap_backend)
        apply_camera_configuration(capture, self._config)

        success, image = capture.read()

        if not success or image is None:
            raise FailedToReadFrameFromCameraException(
                f"Failed to read frame from camera with config: {pprint.pformat(self._config)} "
                f"returned value: {success}, "
                f"returned image: {image}"
            )

        logger.success(f"Successfully connected to Camera: {self._config.camera_id}!")
        self._is_capturing_event.set()
        return capture

    def stop(self):
        logger.debug("Stopping frame capture loop...")
        self._should_run_frame_loop = False
        if self._cv2_video_capture is not None:
            self._cv2_video_capture.release()

    def update_camera_config(self, new_config: CameraConfig):
        self._config = new_config
        logger.info(f"Updating Camera: {self._config.camera_id} config to {new_config}")
        apply_camera_configuration(self._cv2_video_capture, new_config)


if __name__ == "__main__":
    config = CameraConfig(camera_id=0)
    con1, con2 = multiprocessing.Pipe()
    event1 = multiprocessing.Event()
    event2 = multiprocessing.Event()
    event2.set()
    thread = VideoCaptureThread(config=config,
                                pipe=con1,
                                is_capturing_event=event1,
                                all_cameras_ready_event=event2)
    thread.start()
    #
    # cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # # apply_camera_configuration(cap, CameraConfig(camera_id=0))
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    # fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    # cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    # previous_timestamp = time.perf_counter()
    # while True:
    #     success, image = cap.read()
    #     timestamp = time.perf_counter()
    #     print(f"FPS: {1 / (timestamp - previous_timestamp)} - image.shape: {image.shape}")
    #     previous_timestamp = timestamp
