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
            this_camera_ready_event: multiprocessing.Event,
            all_cameras_ready_event: multiprocessing.Event,
    ):
        super().__init__()
        self._previous_timestamp = time.perf_counter()
        self._pipe = pipe
        self._new_frame_ready = False
        self.daemon = False

        self._this_camera_ready_event = this_camera_ready_event
        self._all_cameras_ready_event = all_cameras_ready_event

        self._config = config
        self._is_capturing_frames = False

        self._cv2_video_capture = None

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
        while not self._all_cameras_ready_event.is_set():
            time.sleep(.001)
            continue
        self._is_capturing_frames = True
        frame_number = -1
        camera_id = self._config.camera_id
        previous_timestamp = time.perf_counter()
        while self._is_capturing_frames:
            success, image = self._cv2_video_capture.read()
            retrieval_timestamp = time.perf_counter()
            frame_number += 1
            FramePayload.create(
                success=success,
                image=image,
                timestamp_ns=int(retrieval_timestamp),
                frame_number=frame_number,
                camera_id=camera_id,
            )
            logger.trace(f"CAMERA_ID: {camera_id} - FPS: {1 / (retrieval_timestamp - previous_timestamp)} - image.shape: {image.shape}")
            previous_timestamp = retrieval_timestamp
            # self._pipe.send_bytes(self._frame.to_bytes())

        self.stop()
        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has exited"
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
        self._this_camera_ready_event.set()
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


if __name__ == "__main__":
    config = CameraConfig(camera_id=0)
    con1, con2 = multiprocessing.Pipe()
    event1 = multiprocessing.Event()
    event2 = multiprocessing.Event()
    event2.set()
    thread = VideoCaptureThread(config=config,
                                pipe=con1,
                                this_camera_ready_event=event1,
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
