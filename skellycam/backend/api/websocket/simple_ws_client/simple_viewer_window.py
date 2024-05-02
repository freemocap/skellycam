import logging
import time
from typing import List

import cv2
import numpy as np
from pydantic import BaseModel

from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class SimpleViewerWindow(BaseModel):
    window_name: str
    framerate: float = 30
    should_quit: bool = False

    frames_received: int = 0
    frames_shown: int = 0
    draw_times: List[float] = []
    frames_skipped: int = 0

    @classmethod
    def from_camera_id(cls, camera_id: CameraId, framerate: float):
        if not isinstance(camera_id, CameraId):
            raise ValueError(f"camera_id must be of type CameraId. Got: {type(camera_id)}")
        if framerate <= 0:
            raise ValueError(f"framerate must be greater than 0. Got: {framerate}")

        return cls(window_name=cls._make_window_name(camera_id),
                   framerate=framerate)

    @property
    def draw_fps(self):
        if len(self.draw_times) < 2:
            return 0
        return 1 / np.mean(np.diff(self.draw_times))

    @property
    def percent_frames_shown(self):
        return self.frames_shown / self.frames_received * 100 if self.frames_received > 0 else None

    @property
    def ideal_frame_duration(self):
        return 1 / self.framerate

    @property
    def time_since_last_draw(self):
        return time.perf_counter() - self.draw_times[-1] if self.draw_times else 0

    def show_frame(self, jpeg_image: bytes):
        try:
            self.frames_received += 1
            image_rgb = self._convert_image(jpeg_image)

            if self._should_draw_frame() or True:
                self.frames_shown += 1
                self._draw_frame(image_rgb)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.info("User pressed 'q'. Quitting viewer....")
                self.quit()
        except Exception as e:
            logger.error(f"An error occurred while displaying frame: {e}")
            logger.exception(e)
            raise

    def _should_draw_frame(self) -> bool:
        time_since_last_draw = time.perf_counter() - self.draw_times[-1] if self.draw_times else 0
        if time_since_last_draw < self.ideal_frame_duration:
            self.frames_skipped += 1
            return False
        return True

    def _draw_frame(self, image_rgb):
        cv2.imshow(self.window_name, self._annotate_image(image_rgb))
        self.frames_shown += 1
        self.draw_times.append(time.perf_counter())

    def _annotate_image(self, image_rgb: np.ndarray) -> np.ndarray:
        annotated_image = image_rgb
        annotated_image = cv2.putText(annotated_image, f"Camera ID: {self.window_name}", (10, 30),
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        annotated_image = cv2.putText(annotated_image, f"Frames Received: {self.frames_received}", (10, 60),
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        annotated_image = cv2.putText(annotated_image, f"Viewer FPS: {self.draw_fps:.2f} (Ideal FPS: {self.framerate})",
                                      (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        annotated_image = cv2.putText(annotated_image, f"% Frames Shown: {self.percent_frames_shown:.2f}", (10, 120),
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        annotated_image = cv2.putText(annotated_image, f"Time Since Last Draw: {self.time_since_last_draw:.2f}",
                                      (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        return annotated_image

    def quit(self):
        cv2.destroyWindow(self.window_name)
        self.should_quit = True

    @staticmethod
    def _convert_image(jpeg_image: bytes):
        np_arr = np.frombuffer(jpeg_image, np.uint8)
        image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        return image_rgb

    @staticmethod
    def _make_window_name(camera_id: CameraId):
        return f'Camera {camera_id} - Press `Q` to quit'
