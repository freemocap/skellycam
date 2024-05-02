import time
from typing import List

import cv2
import numpy as np
from pydantic import BaseModel

from skellycam.backend.api.websocket.simple_ws_client.simple_viewer import logger
from skellycam.backend.core.device_detection.camera_id import CameraId


class SimpleViewerWindow(BaseModel):
    window_name: str
    should_quit: bool = False

    _frames_received: int = 0
    _frames_shown: int = 0
    _draw_times: List[float] = []
    _framerate: float = 30
    _skip_n_frames_per_second: int = 0
    _lag_buffer: float = .8
    _frames_skipped_total: int = 0
    _frames_skipped_since_last_reset: int = 0
    _skip_count_reset_timestamp: float = time.perf_counter()

    @classmethod
    def from_camera_id(cls, camera_id: CameraId):
        return cls(window_name=cls._make_window_name(camera_id))

    @property
    def draw_fps(self):
        if len(self._draw_times) < 2:
            return 0
        return 1 / np.mean(np.diff(self._draw_times))

    @property
    def ideal_frame_duration(self):
        return 1 / self._framerate

    @property
    def time_since_last_draw(self):
        return time.perf_counter() - self._draw_times[-1] if self._draw_times else 0

    def show_frame(self, jpeg_image: bytes):
        self._frames_received += 1
        image_rgb = self._convert_image(jpeg_image)

        if self._should_draw_frame():
            self._frames_shown += 1
            self._draw_frame(image_rgb)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("User pressed 'q'. Quitting viewer....")
            self.quit()

    def _draw_frame(self, image_rgb):
        cv2.imshow(self.window_name, image_rgb)
        self._frames_shown += 1
        self._draw_times.append(time.perf_counter())

    def quit(self):
        cv2.destroyWindow(self.window_name)
        self.should_quit = True

    def _should_draw_frame(self) -> bool:
        time_since_last_draw = time.perf_counter() - self._draw_times[-1] if self._draw_times else 0

        if time_since_last_draw < self.ideal_frame_duration * self._lag_buffer:
            if self._skip_n_frames_per_second > 0:

                self._skip_n_frames_per_second -= 1

        if time.perf_counter() - self._skip_count_reset_timestamp > 1:
            self._frames_skipped_since_last_reset = 0
        else:
            if self._frames_skipped_since_last_reset < self._skip_n_frames_per_second:
                self._frames_skipped_since_last_reset += 1
                self._frames_skipped_total += 1
                return False

        if time_since_last_draw > self.ideal_frame_duration:
            if self._skip_n_frames_per_second < self._framerate:
                logger.debug(f"Time since last draw: {time_since_last_draw} is greater than ideal frame duration: {self.ideal_frame_duration}. Skipping frame...")
                self._skip_n_frames_per_second += 1
                self._skip_count_reset_timestamp = time.perf_counter()
                return False

        return True

    @staticmethod
    def _convert_image(jpeg_image: bytes):
        np_arr = np.frombuffer(jpeg_image, np.uint8)
        image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        return image_rgb

    @staticmethod
    def _make_window_name(camera_id: CameraId):
        return f'Camera {camera_id} - Press `Q` to quit'
