import logging
from typing import Dict, Optional

import cv2
import numpy as np

from skellycam.backend.core.device_detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class SimpleViewer:
    def __init__(self):
        self.windows_initialized = False
        self.should_quit = False

    def display_images(self, jpeg_images: Dict[CameraId, Optional[bytes]]):
        for camera_id, jpeg_image in jpeg_images.items():
            if not jpeg_image:
                continue

            window_name = f'Camera {camera_id} - Press Q to quit'
            if not self.windows_initialized:
                # Initialize the window for this camera
                cv2.namedWindow(window_name)
                self.windows_initialized = True

            # Display the image
            np_arr = np.frombuffer(jpeg_image, np.uint8)

            image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            cv2.imshow(window_name, image_rgb)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("User pressed 'q'. Quitting viewer....")
            self.quit()

    def quit(self):
        cv2.destroyAllWindows()
        self.should_quit = True
