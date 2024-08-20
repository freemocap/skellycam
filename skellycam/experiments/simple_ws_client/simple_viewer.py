import logging
from typing import Dict

import cv2
from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.experiments.simple_ws_client.simple_viewer_window import SimpleViewerWindow

logger = logging.getLogger(__name__)


class SimpleViewer(BaseModel):
    should_quit: bool = False
    prescribed_framerate = 30
    windows: Dict[CameraId, SimpleViewerWindow] = {}

    def display_images(self, frontend_payload: FrontendFramePayload):
        try:
            for camera_id, jpeg_image in frontend_payload.jpeg_images_by_camera.items():
                if not jpeg_image:
                    continue
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
