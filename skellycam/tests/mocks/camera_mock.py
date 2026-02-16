import time
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class MockVideoCapture:
    def __init__(self, index=0, backend=None):
        self._is_opened = True
        self._frame_count = 0
        self._width = 640.0
        self._height = 480.0
        self._fps = 30.0
        self._exposure = -5.0  # Common value for default exposure
        self._last_frame_time = time.time()
        self._start_time = time.time()
        
        # Mapping of property IDs to internal attributes
        self._prop_map = {
            cv2.CAP_PROP_FRAME_WIDTH: '_width',
            cv2.CAP_PROP_FRAME_HEIGHT: '_height',
            cv2.CAP_PROP_FPS: '_fps',
            cv2.CAP_PROP_EXPOSURE: '_exposure',
        }

    def isOpened(self) -> bool:
        return self._is_opened

    def release(self):
        self._is_opened = False

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._is_opened:
            return False, None

        # Simulate blocking behavior to match FPS
        target_interval = 1.0 / self._fps
        now = time.time()
        elapsed = now - self._last_frame_time
        
        if elapsed < target_interval:
            sleep_time = target_interval - elapsed
            time.sleep(sleep_time)
            
        self._last_frame_time = time.time()
        self._frame_count += 1
        
        return True, self._generate_frame()

    def _generate_frame(self) -> np.ndarray:
        # Create a black frame
        frame = np.zeros((int(self._height), int(self._width), 3), dtype=np.uint8)
        
        # Define text parameters
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        color = (255, 255, 255)  # White
        thickness = 2
        line_height = 30
        start_x = 10
        start_y = 40
        
        info_lines = [
            f"Frame: {self._frame_count}",
            f"Time: {time.time() - self._start_time:.3f}s",
            f"FPS: {self._fps:.1f}",
            f"Res: {int(self._width)}x{int(self._height)}",
            f"Exp: {self._exposure:.1f}",
            f"Mock Camera",
        ]

        for i, line in enumerate(info_lines):
            y = start_y + (i * line_height)
            cv2.putText(frame, line, (start_x, y), font, font_scale, color, thickness, cv2.LINE_AA)
            
        return frame

    def set(self, propId: int, value: float) -> bool:
        if not self._is_opened:
            return False

        if propId == cv2.CAP_PROP_FPS:
            if value > 100 or value <= 0:
                logger.warning(f"Attempted to set invalid FPS: {value}")
                return False
            self._fps = float(value)
            return True
            
        elif propId == cv2.CAP_PROP_FRAME_WIDTH:
            if value > 4096 or value <= 0:
                return False
            self._width = float(value)
            return True
            
        elif propId == cv2.CAP_PROP_FRAME_HEIGHT:
            if value > 2160 or value <= 0:
                return False
            self._height = float(value)
            return True
            
        elif propId == cv2.CAP_PROP_EXPOSURE:
            # Exposure range depends on camera, but -15 to 10 is a reasonable mock range or similar
            # OpenCV often uses powers of 2 for exposure time, but here we just store the value
            self._exposure = float(value)
            return True

        return False

    def get(self, propId: int) -> float:
        if propId in self._prop_map:
            attr_name = self._prop_map[propId]
            return getattr(self, attr_name)
        elif propId == cv2.CAP_PROP_POS_FRAMES:
             return float(self._frame_count)
        elif propId == cv2.CAP_PROP_POS_MSEC:
             return (time.time() - self._start_time) * 1000.0
        return 0.0
