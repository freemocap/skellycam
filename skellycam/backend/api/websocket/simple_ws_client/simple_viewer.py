import logging
from typing import Dict, Optional

import cv2
from pydantic import BaseModel

from skellycam.backend.api.websocket.simple_ws_client.simple_viewer_window import SimpleViewerWindow
from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class SimpleViewer(BaseModel):
    should_quit: bool = False
    prescribed_framerate = 30
    windows: Dict[CameraId, SimpleViewerWindow] = {}

    def display_images(self, jpeg_images: Dict[CameraId, Optional[bytes]]):
        try:
            for camera_id, jpeg_image in jpeg_images.items():
                if not jpeg_image:
                    continue
                logger.trace(f"Jpeg image received for camera {camera_id} - {jpeg_image[:50]}...{jpeg_image[-50:]}")
                if camera_id not in self.windows:
                    self.windows[camera_id] = SimpleViewerWindow.from_camera_id(camera_id, self.prescribed_framerate)
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
