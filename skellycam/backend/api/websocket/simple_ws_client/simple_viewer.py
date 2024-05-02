import logging
from typing import Dict, Optional

import cv2

from skellycam.backend.api.websocket.simple_ws_client.simple_viewer_window import SimpleViewerWindow
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class SimpleViewer:
    def __init__(self):
        self.should_quit = False
        self._prescribed_framerate = 30
        self.windows = {}

    def display_images(self, jpeg_images: Dict[CameraId, Optional[bytes]]):
        try:
            for camera_id, jpeg_image in jpeg_images.items():
                if not jpeg_image:
                    continue

                if camera_id not in self.windows:
                    self.windows[camera_id] = SimpleViewerWindow.from_camera_id(camera_id, self._prescribed_framerate)
                self.windows[camera_id].show_frame(jpeg_image)
                if any([window.should_quit for window in self.windows.values()]):
                    self.quit()
                    break

        except Exception as e:
            logger.error(f"An error occurred while displaying images: {e}")
            logger.exception(e)
            raise

    def quit(self):
        cv2.destroyAllWindows()
        self.should_quit = True
