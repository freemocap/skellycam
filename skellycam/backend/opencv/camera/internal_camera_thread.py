import io
import logging
import multiprocessing
import threading
import time
import traceback

import cv2
from PIL import Image

from skellycam.backend.opencv.config.apply_config import apply_configuration
from skellycam.backend.opencv.config.determine_backend import determine_backend
from skellycam.data_models.camera_config import CameraConfig
from skellycam.data_models.frame_payload import FramePayload

logger = logging.getLogger(__name__)

def compress_image(image,
                   quality: int) -> bytes:
    # Image compression
    image_pil = Image.fromarray(image)
    byte_arr = io.BytesIO()
    image_pil.save(byte_arr, format='JPEG', quality=quality) #adjust quality as per requirement`
    image_compressed = byte_arr.getvalue()
    return image_compressed

class VideoCaptureThread(threading.Thread):
    def __init__(
            self,
            config: CameraConfig,
            ready_event: multiprocessing.Event,
            compression: bool = True,
    ):
        super().__init__()
        self._ready_event = ready_event
        self._config = config
        self._compression = compression

        self.daemon = False
        self._is_capturing_frames = False
        self._new_frame_ready = False
        self._number_of_frames_received: int = 0

        self._cv2_video_capture = self._create_cv2_capture()

    @property
    def new_frame_ready(self) -> bool:
        return self._new_frame_ready

    @property
    def latest_frame(self) -> FramePayload:
        self._new_frame_ready = False
        return self._frame

    @property
    def is_capturing_frames(self) -> bool:
        """Is the thread capturing frames from the cameras (but not necessarily recording them, that's handled by `is_recording_frames`)"""
        return self._is_capturing_frames

    def run(self):
        self._start_frame_loop()

    def _start_frame_loop(self):
        self._is_capturing_frames = True
        logger.success(
            f"Camera ID: [{self._config.camera_id}] Frame capture loop has started"
        )
        try:
            while self._is_capturing_frames:
                self._frame = self._get_next_frame()
                if self._frame.success:
                    self._new_frame_ready = True
        except Exception as e:
            logger.error(
                f"Camera ID: [{self._config.camera_id}] Frame loop thread exited due to error"
            )
            logger.exception(e)
            raise e
        finally:
            self._is_capturing_frames = False
            self._cv2_video_capture.release()

    def _get_next_frame(self) -> FramePayload:
        success, image = self._cv2_video_capture.read()  # <- THIS IS WHERE THE MAGIC HAPPENS (i.e. the actual frame capture, aka the actual "measurement", aka the "moment of transduction", aka "the moment where environmental energy (light) is transcduced into a pattern of electrical energy (pixels) on a sensor (the camera's sensor)")
        retrieval_timestamp = time.perf_counter_ns()

        if self._compression:
            image = compress_image(image, quality=20) #the safest time to do this is right after a frame read bc we have the most time. Decrease quality to increase speed

        if success:
            self._number_of_frames_received += 1
            return FramePayload(
                success=success,
                image=image,
                timestamp_ns=retrieval_timestamp,
                number_of_frames_received=self._number_of_frames_received,
                camera_id=str(self._config.camera_id),
                compression='JPEG' if self._compression else "raw",
            )
        else:
            logger.error(
                f"Failed to read frame from camera at port# {self._config.camera_id}: "
                f"returned value: {success}, "
                f"returned image: {image}"
            )

    def _create_cv2_capture(self):
        logger.info(f"Connecting to Camera: {self._config.camera_id}...")
        cap_backend = determine_backend()

        try:
            self._cv2_video_capture.release()
        except Exception as e:
            logger.trace(e)
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
