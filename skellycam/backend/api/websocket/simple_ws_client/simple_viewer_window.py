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
    camera_id: CameraId
    framerate: float = 30
    should_quit: bool = False
    should_annotate_image: bool = True

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

        return cls(camera_id=camera_id,
                   framerate=framerate)

    @property
    def window_name(self):
        return f'Camera {self.camera_id} - `A` toggle annotation, `Q` or ESC to quit'

    @property
    def draw_fps(self):
        if len(self.draw_times) < 2:
            return 0
        return 1 / np.mean(np.diff(self.draw_times))

    @property
    def percent_frames_shown(self):
        return (self.frames_shown / self.frames_received) * 100 if self.frames_received > 0 else None

    @property
    def ideal_frame_duration(self):
        return 1 / self.framerate

    @property
    def time_since_last_draw_ms(self):
        time_since = time.perf_counter() - self.draw_times[-1] if self.draw_times else 0
        return time_since * 1000

    def show_frame(self, jpeg_image: bytes):
        try:
            self.frames_received += 1
            image_rgb = self._convert_image(jpeg_image)

            if self._should_draw_frame() or True:
                self.frames_shown += 1
                self._draw_frame(image_rgb)
            else:
                self.frames_skipped += 1

            self._keyboard_listener()
        except Exception as e:
            logger.error(f"An error occurred while displaying frame: {e}")
            logger.exception(e)
            raise

    def _keyboard_listener(self):
        # Wait for a key press and check for 'q', 'a', and 'ESC' keys
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # 'q' or 'ESC' key
            logger.info("User pressed 'q' or 'ESC'. Quitting viewer....")
            self.quit()
        elif key == ord('a'):  # 'a' key
            # Toggle annotation
            self.should_annotate_image = not self.should_annotate_image
            logger.info(f"Annotation {'enabled' if self._annotate_image else 'disabled'}.")

    def _should_draw_frame(self) -> bool:
        time_since_last_draw = time.perf_counter() - self.draw_times[-1] if self.draw_times else 0
        if time_since_last_draw < self.ideal_frame_duration:
            return False
        return True

    def _draw_frame(self, image_rgb):
        if self.should_annotate_image:
            cv2.imshow(self.window_name, self._annotate_image(image_rgb))
        else:
            cv2.imshow(self.window_name, image_rgb)
        self.draw_times.append(time.perf_counter())

    def _annotate_image(self, image_rgb: np.ndarray) -> np.ndarray:
        annotation_text = [
            f"Camera ID: {self.window_name}",
            f"Frames Received: {self.frames_received} - Frames Skipped: {self.frames_skipped}",
            f"Viewer FPS: {self.draw_fps:.2f} (Ideal FPS: {self.framerate})",
            f"% Frames Shown: {self.percent_frames_shown:.2f}",
            f"Time Since Last Draw: {self.time_since_last_draw_ms:.2f} ms"
        ]
        font_scale = 0.5
        font_thickness = 1
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_outline_thickness = 2
        font_outline_color = (0, 0, 0)
        font_color = (255, 0, 255)
        font_position = (10, 20)  # Starting position (x, y)
        font_line_type = cv2.LINE_AA
        line_gap = 20  # Gap between lines

        annotated_image = image_rgb
        for i, line in enumerate(annotation_text):
            y_pos = font_position[1] + i * line_gap
            #draw text outline
            annotated_image = cv2.putText(annotated_image, line, (font_position[0], y_pos), font,
                                          font_scale, font_outline_color, font_outline_thickness, font_line_type)
            #draw text
            annotated_image = cv2.putText(annotated_image, line, (font_position[0], y_pos), font,
                                          font_scale, font_color, font_thickness, font_line_type)

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

