import logging
import multiprocessing
import threading
import time
import traceback

import cv2

from skellycam.backend.opencv.config.apply_config import apply_configuration
from skellycam.backend.opencv.config.determine_backend import determine_backend
from skellycam.data_models.camera_config import CameraConfig
from skellycam.data_models.frame_payload import FramePayload, SharedMemoryFramePayload

logger = logging.getLogger(__name__)


class VideoCaptureThread(threading.Thread):
    def __init__(
            self,
            config: CameraConfig,
            frame_queue: multiprocessing.Queue,
            ready_event: multiprocessing.Event,
    ):
        super().__init__()
        self._frame_queue = frame_queue
        self.daemon = False

        self._ready_event = ready_event

        self._config = config
        self._is_capturing_frames = False

        self._number_of_frames_received: int = 0

        self._capture_timestamps = []
        self._mean_frames_per_second = None
        self._cv2_video_capture = self._create_cv2_capture()

    @property
    def is_capturing_frames(self) -> bool:
        """Is the thread capturing frames from the cameras (but not necessarily recording them, that's handled by `is_recording_frames`)"""
        return self._is_capturing_frames

    def run(self):
        self._start_frame_loop()

    def _start_frame_loop(self):
        self._is_capturing_frames = True
        logger.info(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has started"
        )
        try:
            while self._is_capturing_frames:
                frame = self._get_next_frame()
                self._frame_queue.put(frame)
        except Exception as e:
            logger.error(
                f"Camera ID: [{self._config.camera_id}] Frame loop thread exited due to error"
            )
            logger.exception(e)
            raise e

    def _get_next_frame(self) -> FramePayload:
        success,image = self._cv2_video_capture.read()  # <- THIS IS WHERE THE MAGIC HAPPENS (i.e. the actual frame capture, aka the actual "measurement", aka the "moment of transduction", aka "the moment where environmental energy (light) is transcduced into a pattern of electrical energy (pixels) on a sensor (the camera's sensor)")
        retrieval_timestamp = time.perf_counter_ns()

        if success:
            self._new_frame_ready = True
            self._number_of_frames_received += 1
        else:
            logger.error(
                f"Failed to read frame from camera at port# {self._config.camera_id}: "
                f"returned value: {success}, "
                f"returned image: {image}"
            )

        reg_frame_tik = time.perf_counter()
        frame_payload = FramePayload(
            success=success,
            image=image,
            timestamp_ns=retrieval_timestamp,
            number_of_frames_received=self._number_of_frames_received,
            camera_id=str(self._config.camera_id),
        )
        reg_frame_tok = time.perf_counter()
        reg_enqueue_tik = time.perf_counter()
        self._frame_queue.put(frame_payload)
        reg_enqueue_tok = time.perf_counter()

        shared_frame_tik = time.perf_counter()
        shared_frame_payload = SharedMemoryFramePayload.from_data(success=success,
                                                                  image=image,
                                                                  timestamp_ns=retrieval_timestamp,
                                                                  number_of_frames_received=self._number_of_frames_received,
                                                                  camera_id=str(self._config.camera_id))
        shared_frame_tok = time.perf_counter()
        shared_enqueue_tik = time.perf_counter()
        self._frame_queue.put(shared_frame_payload)
        shared_enqueue_tok = time.perf_counter()

        logger.info(f"It took {reg_frame_tok - reg_frame_tik:.6f} seconds to create a regular frame payload.\n"
                    f"It took {reg_enqueue_tok - reg_enqueue_tik:.6f} seconds to enqueue a regular frame payload.\n"
                    f"It took {shared_frame_tok - shared_frame_tik:.6f} seconds to create a shared frame payload.\n"
                    f"It took {shared_enqueue_tok - shared_enqueue_tik:.6f} seconds to enqueue a shared frame payload.\n")
        return frame_payload

    def _create_cv2_capture(self):
        logger.info(f"Connecting to Camera: {self._config.camera_id}...")
        cap_backend = determine_backend()

        try:
            self._cv2_video_capture.release()
        except:
            pass

        capture = cv2.VideoCapture(int(self._config.camera_id), cap_backend)

        try:
            success, image = capture.read()
        except Exception as e:
            logger.error(
                f"Problem when trying to read frame from Camera: {self._config.camera_id}"
            )
            traceback.print_exc()
            raise e

        if not success or image is None:
            logger.error(
                f"Failed to read frame from camera at port# {self._config.camera_id}: "
                f"returned value: {success}, "
                f"returned image: {image} - releasing, closing, and deleting capture object and re-running self._create_cv2_capture()"
            )
            capture.release()
            del capture
            return self._create_cv2_capture()

        apply_configuration(capture, self._config)

        logger.info(f"Successfully connected to Camera: {self._config.camera_id}!")
        if not self._ready_event.is_set():
            self._ready_event.set()

        return capture

    def stop(self):
        self._is_capturing_frames = False
        if self._cv2_video_capture is not None:
            logger.debug(
                f"Releasing `opencv_video_capture_object` for Camera: {self._config.camera_id}"
            )
            self._cv2_video_capture.release()

    def update_camera_config(self, new_config: CameraConfig):
        self._config = new_config
        logger.info(f"Updating Camera: {self._config.camera_id} config to {new_config}")
        apply_configuration(self._cv2_video_capture, new_config)
